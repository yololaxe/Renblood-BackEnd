"""Character registration sidecar. Existing players and economic balances stay authoritative."""
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import logging
import re
import secrets
import time
from uuid import UUID

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from firebase_admin import auth
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from economy.store import get_bank
from players.models import Player
from utils.decorators import _has_server_api_key

logger = logging.getLogger(__name__)
PORTRAITS = [
    {"id": "wanderer", "label": "Voyageur"}, {"id": "scholar", "label": "Érudite"},
    {"id": "guard", "label": "Garde"}, {"id": "artisan", "label": "Artisan"},
    {"id": "ranger", "label": "Éclaireuse"}, {"id": "sailor", "label": "Marin"},
]
FIELDS = {"name": 60, "surname": 60, "description": 2000, "origin": 120, "portrait": 24}
DEFAULT_SETTINGS = {"mode": "OPEN", "starting_rank": "Citoyen", "require_minecraft": False,
    "required_fields": ["name", "surname"], "name_policy": "REVIEW_AFTER_VALIDATION",
    "portraits": [item["id"] for item in PORTRAITS], "revision": 0}
JOBS = ("lumberjack", "naval_architect", "artisan", "carpenter", "miner", "blacksmith", "glassmaker", "mason",
        "farmer", "breeder", "fisherman", "innkeeper", "guard", "merchant", "transporter", "explorer",
        "bestiary", "banker", "politician", "builder")


def initial_jobs():
    return {"jobs": {job: {"xp": -1, "level": 0,
        "progression": [False] * (15 if job in {"bestiary", "banker", "politician", "builder"} else 10),
        "inter_choice": [], "choose_lvl_10": ""} for job in JOBS}}


class ProfileError(Exception):
    def __init__(self, code, message, status=400, fields=None):
        super().__init__(message)
        self.code, self.status, self.fields = code, status, fields or {}


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical_uuid(value):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def visible(document):
    return {key: value for key, value in document.items() if key != "_id"}


class Profiles:
    def __init__(self, bank):
        self.bank, self.db = bank, bank.db
        self.profiles = self.db.player_registration_profiles
        self.settings_collection = self.db.player_registration_settings
        self.codes = self.db.player_registration_link_codes
        self.links = self.db.player_registration_links

    def settings(self, session=None):
        saved = self.settings_collection.find_one({"_id": "registration"}, session=session) or {}
        return {**deepcopy(DEFAULT_SETTINGS), **visible(saved)}

    def initial(self, uid, session):
        player = self.db.players.find_one({"id": uid}, session=session)
        minecraft = canonical_uuid((player or {}).get("id_minecraft"))
        return {"_id": uid, "id": uid, "revision": 0,
            "status": "ACTIVE" if player else "DRAFT", "legacy": bool(player),
            "name": (player or {}).get("name", ""), "surname": (player or {}).get("surname", ""),
            "description": (player or {}).get("description", "") or "", "origin": "",
            "portrait": self.settings(session)["portraits"][0],
            "minecraft": {"uuid": minecraft, "username": (player or {}).get("pseudo_minecraft", "") if minecraft else "",
                          "verified": bool(minecraft), "legacy": bool(minecraft)},
            "pending_changes": None, "pending_minecraft": None, "history": [],
            "starting_rank": (player or {}).get("rank", self.settings(session)["starting_rank"]),
            "updated_at": now()}

    def get(self, uid, session=None):
        return self.profiles.find_one({"_id": uid}, session=session)

    def other_minecraft_owner(self, uuid, uid, session):
        # Also protect legacy UUIDs saved uppercase or without hyphens.
        raw = UUID(uuid).hex
        groups = (raw[:8], raw[8:12], raw[12:16], raw[16:20], raw[20:])
        return self.db.players.find_one({"id": {"$ne": uid},
            "id_minecraft": {"$regex": "^" + "-?".join(groups) + "$", "$options": "i"}}, session=session)

    def bootstrap(self, uid):
        def execute(session):
            profile = self.get(uid, session)
            if profile:
                return profile
            profile = self.initial(uid, session)
            self.profiles.insert_one(profile, session=session)
            return profile
        try:
            return self.bank.transact(execute)
        except DuplicateKeyError:
            existing = self.get(uid)
            if existing:
                return existing
            raise

    def check_revision(self, profile, body):
        revision = body.get("revision")
        if type(revision) is not int or revision != profile["revision"]:
            raise ProfileError("REVISION_CONFLICT", "Ce dossier a changé dans une autre fenêtre. Rechargez-le avant de continuer.", 409)

    def validate_fields(self, values, settings, complete=False):
        if not isinstance(values, dict):
            raise ProfileError("INVALID_PROFILE", "Un ensemble de champs est attendu.")
        errors, cleaned = {}, {}
        for field, value in values.items():
            if field not in FIELDS:
                raise ProfileError("INVALID_FIELD", "Ce champ ne fait pas partie du profil modifiable.", fields={field: "Modification non autorisée."})
            if not isinstance(value, str):
                errors[field] = "Un texte est attendu."
                continue
            value = value.strip()
            if len(value) > FIELDS[field]:
                errors[field] = f"Maximum {FIELDS[field]} caractères."
            elif field in {"name", "surname", "origin"} and any(ord(c) < 32 for c in value):
                errors[field] = "Les caractères de contrôle ne sont pas acceptés."
            elif field == "portrait" and value not in settings["portraits"]:
                errors[field] = "Choisissez un portrait disponible."
            cleaned[field] = value
        if complete:
            for field in settings["required_fields"]:
                if not values.get(field, "").strip():
                    errors[field] = "Ce champ est obligatoire."
        if errors:
            raise ProfileError("INVALID_PROFILE", "Vérifiez les champs indiqués.", fields=errors)
        return cleaned

    def record(self, profile, actor, action, details=None):
        profile["revision"] += 1
        profile["updated_at"] = now()
        profile["history"] = (profile.get("history", []) + [
            {"at": now(), "actor": actor, "action": action, "details": details or {}}])[-100:]

    def sync_player(self, profile, session):
        """Materialize only a completed, accepted character with a verified MC identity."""
        if profile["status"] != "ACTIVE" or not profile["minecraft"].get("verified"):
            return
        uid, minecraft = profile["id"], profile["minecraft"]
        conflict = self.other_minecraft_owner(minecraft["uuid"], uid, session)
        if conflict:
            raise ProfileError("MINECRAFT_IN_USE", "Ce compte Minecraft appartient déjà à un autre personnage.", 409)
        # These are identity fields only: never replace progress, rank, money or licences.
        identity = {key: profile[key] for key in ("name", "surname", "description")}
        identity.update(id_minecraft=minecraft["uuid"], pseudo_minecraft=minecraft["username"])
        existing = self.db.players.find_one({"id": uid}, session=session)
        if existing:
            self.db.players.update_one({"id": uid}, {"$set": identity}, session=session)
        else:
            player = Player(id=uid, **identity, rank=profile["starting_rank"], money=0,
                            divin="Aucun", experiences=initial_jobs())
            document = {field.attname: getattr(player, field.attname) for field in Player._meta.concrete_fields}
            self.db.players.insert_one(document, session=session)

    def snapshot(self, uid):
        profile = self.get(uid)
        settings = self.settings()
        player = self.db.players.find_one({"id": uid}, {"_id": 0, "id": 1, "rank": 1})
        bank_ready = bool(self.db.economy_accounts.find_one({"_id": "bank:" + uid}, {"_id": 1}))
        return {"profile": visible(profile), "settings": settings, "portrait_options": PORTRAITS,
                "player_ready": bool(player), "rank": (player or {}).get("rank"),
                "missing_fields": [field for field in settings["required_fields"] if not profile.get(field, "").strip()],
                "needs_onboarding": profile["status"] == "DRAFT", "bank_ready": bank_ready}

    def prepare_bank(self, uid):
        # Only profiles materialized by the new flow; legacy balances require their usual migration review.
        profile = self.get(uid)
        if not profile or profile.get("legacy") or profile["status"] != "ACTIVE" or not profile["minecraft"].get("verified"):
            return
        if self.db.economy_accounts.find_one({"_id": "bank:" + uid}, {"_id": 1}):
            return
        try:
            self.bank.migrate(uid, apply=True, expected_balance="0")
        except Exception:
            # Character is already committed. An idempotent retry can finish bank setup later.
            logger.exception("New character bank preparation pending uid=%s", uid)

    def edit(self, uid, body):
        def execute(session):
            profile = self.get(uid, session)
            self.check_revision(profile, body)
            settings = self.settings(session)
            if profile["status"] != "DRAFT" and profile["portrait"] not in settings["portraits"]:
                # Disabling a portrait for new choices does not revoke an existing selection.
                settings = {**settings, "portraits": settings["portraits"] + [profile["portrait"]]}
            values = self.validate_fields(body.get("fields", {}), settings)
            if profile["status"] != "DRAFT":
                combined = {field: values.get(field, profile[field]) for field in FIELDS}
                self.validate_fields(combined, settings, complete=True)
            names = {field: value for field, value in values.items()
                     if field in {"name", "surname"} and value != profile[field]}
            if names and profile["status"] == "ACTIVE" and settings["name_policy"] != "FREE":
                previous_request = {key: value for key, value in (profile.get("pending_changes") or {}).items() if key in {"name", "surname"}}
                profile["pending_changes"] = {**previous_request, **names, "requested_at": now()}
                values = {field: value for field, value in values.items() if field not in names}
            previous = {key: profile[key] for key in values if profile[key] != values[key]}
            profile.update(values)
            self.record(profile, uid, "PROFILE_EDITED", {"before": previous,
                "after": {key: profile[key] for key in previous},
                "name_request": deepcopy(profile.get("pending_changes")) if names else None})
            self.sync_player(profile, session)
            self.profiles.replace_one({"_id": uid}, profile, session=session)
        self.bank.transact(execute)
        return self.snapshot(uid)

    def submit(self, uid, body):
        def execute(session):
            profile = self.get(uid, session)
            if profile["status"] in {"ACTIVE", "PENDING"}:
                return  # lost response/double submit: return the already accepted result
            self.check_revision(profile, body)
            settings = self.settings(session)
            if settings["mode"] == "CLOSED":
                raise ProfileError("REGISTRATION_CLOSED", "Les inscriptions sont temporairement suspendues.", 409)
            self.validate_fields({field: profile[field] for field in FIELDS}, settings, complete=True)
            if settings["require_minecraft"] and not profile["minecraft"].get("verified"):
                raise ProfileError("MINECRAFT_REQUIRED", "Associez Minecraft avant de terminer votre inscription.", fields={"minecraft": "Association requise."})
            profile["status"] = "PENDING" if settings["mode"] == "MODERATED" else "ACTIVE"
            profile["starting_rank"] = settings["starting_rank"]
            self.record(profile, uid, "REGISTRATION_SUBMITTED")
            self.sync_player(profile, session)
            self.profiles.replace_one({"_id": uid}, profile, session=session)
        self.bank.transact(execute)
        self.prepare_bank(uid)
        return self.snapshot(uid)

    def issue_code(self, uid):
        issued = time.time()
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        digest = hashlib.sha256(code.encode()).hexdigest()
        def execute(session):
            previous = self.codes.find_one({"_id": uid}, session=session)
            if previous and issued - previous["issued_at"] < 30:
                raise ProfileError("CODE_COOLDOWN", "Attendez 30 secondes entre deux demandes de code.", 429)
            self.codes.replace_one({"_id": uid}, {"_id": uid, "code_hash": digest,
                "issued_at": issued, "expires_at": issued + 600, "state": "PENDING",
                "purge_at": datetime.fromtimestamp(issued + 3600, timezone.utc)}, upsert=True, session=session)
        self.bank.transact(execute)
        return {"code": code, "expires_at": issued + 600, "command": "/mc lier " + code}

    def confirm_code(self, code, minecraft_uuid, username):
        uuid = canonical_uuid(minecraft_uuid)
        if not uuid or not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{3,16}", username):
            raise ProfileError("INVALID_MINECRAFT", "Identité Minecraft invalide.")
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z2-9]{8}", code.upper()):
            raise ProfileError("INVALID_CODE", "Code invalide ou expiré.")
        digest = hashlib.sha256(code.upper().encode()).hexdigest()
        def execute(session):
            link_code = self.codes.find_one({"code_hash": digest}, session=session)
            if not link_code or link_code["expires_at"] < time.time():
                raise ProfileError("INVALID_CODE", "Code invalide ou expiré. Demandez-en un nouveau sur le site.")
            if link_code["state"] == "CLAIMED":
                if link_code.get("minecraft_uuid") != uuid:
                    raise ProfileError("INVALID_CODE", "Ce code a déjà été utilisé.")
                return link_code["_id"]
            uid = link_code["_id"]
            profile = self.get(uid, session)
            reservation = self.links.find_one({"_id": uuid}, session=session)
            other = self.other_minecraft_owner(uuid, uid, session)
            if other or (reservation and reservation["owner_id"] != uid):
                raise ProfileError("MINECRAFT_IN_USE", "Ce compte Minecraft est déjà associé à un autre personnage.", 409)
            self.links.update_one({"_id": uuid}, {"$setOnInsert": {"owner_id": uid}}, upsert=True, session=session)
            identity = {"uuid": uuid, "username": username, "verified": True, "verified_at": now()}
            replacing = profile["minecraft"].get("verified") and profile["minecraft"].get("uuid") != uuid
            if replacing:
                old_request = profile.get("pending_minecraft")
                if old_request and old_request["uuid"] != uuid:
                    self.links.delete_one({"_id": old_request["uuid"], "owner_id": uid}, session=session)
                profile["pending_minecraft"] = identity
            else:
                profile["minecraft"] = identity
            self.record(profile, "minecraft:" + uuid, "MINECRAFT_CHANGE_REQUESTED" if replacing else "MINECRAFT_VERIFIED")
            self.sync_player(profile, session)
            self.profiles.replace_one({"_id": uid}, profile, session=session)
            self.codes.update_one({"_id": uid}, {"$set": {"state": "CLAIMED", "minecraft_uuid": uuid}}, session=session)
            return uid
        try:
            uid = self.bank.transact(execute)
        except DuplicateKeyError:
            raise ProfileError("MINECRAFT_IN_USE", "Ce compte Minecraft est déjà associé à un autre personnage.", 409)
        self.prepare_bank(uid)
        return {"message": "Compte vérifié. Consultez votre dossier sur le site ; un remplacement de compte doit être validé par le staff.",
                "player_ready": bool(self.db.players.find_one({"id": uid}, {"_id": 1}))}

    def review(self, uid, body, actor):
        def execute(session):
            profile = self.get(uid, session)
            if not profile:
                raise ProfileError("NOT_FOUND", "Dossier introuvable.", 404)
            self.check_revision(profile, body)
            before = {key: deepcopy(profile[key]) for key in ("name", "surname", "minecraft")}
            action, reason = body.get("action"), body.get("reason", "")
            if not isinstance(reason, str) or len(reason) > 500:
                raise ProfileError("INVALID_REASON", "Le motif doit contenir au maximum 500 caractères.")
            if not isinstance(action, str):
                raise ProfileError("INVALID_REVIEW", "Choisissez une action de validation.")
            if action.startswith("REJECT") and not reason.strip():
                raise ProfileError("REASON_REQUIRED", "Indiquez un motif pour le joueur.")
            if action == "APPROVE_REGISTRATION" and profile["status"] == "PENDING":
                settings = self.settings(session)
                settings = {**settings, "portraits": list(set(settings["portraits"] + [profile["portrait"]]))}
                self.validate_fields({field: profile[field] for field in FIELDS}, settings, complete=True)
                if settings["require_minecraft"] and not profile["minecraft"].get("verified"):
                    raise ProfileError("MINECRAFT_REQUIRED", "L'association Minecraft est obligatoire.")
                profile["status"] = "ACTIVE"
            elif action == "REJECT_REGISTRATION" and profile["status"] == "PENDING":
                profile["status"] = "DRAFT"
            elif action in {"APPROVE_NAME", "REJECT_NAME"} and profile.get("pending_changes"):
                if action == "APPROVE_NAME":
                    profile.update({key: value for key, value in profile["pending_changes"].items() if key in {"name", "surname"}})
                profile["pending_changes"] = None
            elif action in {"APPROVE_MINECRAFT", "REJECT_MINECRAFT"} and profile.get("pending_minecraft"):
                if action == "APPROVE_MINECRAFT":
                    old_uuid = profile["minecraft"].get("uuid")
                    if old_uuid:
                        self.links.delete_one({"_id": old_uuid, "owner_id": uid}, session=session)
                    profile["minecraft"] = profile["pending_minecraft"]
                else:
                    self.links.delete_one({"_id": profile["pending_minecraft"]["uuid"], "owner_id": uid}, session=session)
                profile["pending_minecraft"] = None
            else:
                raise ProfileError("INVALID_REVIEW", "Cette demande a déjà été traitée ou n'est plus disponible.", 409)
            self.record(profile, actor, action, {"reason": reason.strip(), "before": before,
                "after": {key: deepcopy(profile[key]) for key in before}})
            self.sync_player(profile, session)
            self.profiles.replace_one({"_id": uid}, profile, session=session)
        self.bank.transact(execute)
        self.prepare_bank(uid)
        return self.snapshot(uid)

    def update_settings(self, body, actor):
        allowed = set(DEFAULT_SETTINGS) - {"revision"}
        values = body.get("settings", {})
        if not isinstance(values, dict) or set(values) - allowed:
            raise ProfileError("INVALID_SETTINGS", "Réglages invalides.")
        settings = {**self.settings(), **values}
        self.check_revision(settings, body)
        if not isinstance(settings["mode"], str) or not isinstance(settings["starting_rank"], str) or settings["mode"] not in {"OPEN", "MODERATED", "CLOSED"} or settings["starting_rank"] not in {"Esclave", "Etranger", "Villageois", "Citoyen"}:
            raise ProfileError("INVALID_SETTINGS", "Mode d'inscription ou rang de départ invalide.")
        if type(settings["require_minecraft"]) is not bool or not isinstance(settings["name_policy"], str) or settings["name_policy"] not in {"FREE", "REVIEW_AFTER_VALIDATION"}:
            raise ProfileError("INVALID_SETTINGS", "Règle de modification invalide.")
        required = settings["required_fields"]
        portraits = settings["portraits"]
        if not isinstance(required, list) or any(not isinstance(x, str) for x in required) or not {"name", "surname"} <= set(required) or set(required) - set(FIELDS):
            raise ProfileError("INVALID_SETTINGS", "Prénom et nom sont obligatoires ; les autres champs doivent appartenir au profil.")
        if not isinstance(portraits, list) or not portraits or any(not isinstance(x, str) for x in portraits) or set(portraits) - {item["id"] for item in PORTRAITS}:
            raise ProfileError("INVALID_SETTINGS", "Gardez au moins un portrait de la sélection.")
        def execute(session):
            current = self.settings(session)
            self.check_revision(current, body)
            saved = {**settings, "_id": "registration", "revision": current["revision"] + 1,
                     "updated_by": actor, "updated_at": now()}
            self.settings_collection.replace_one({"_id": "registration"}, saved, upsert=True, session=session)
        self.bank.transact(execute)
        return self.settings()

    def cancel_request(self, uid, body):
        def execute(session):
            profile = self.get(uid, session)
            self.check_revision(profile, body)
            kind = body.get("type")
            if kind == "NAME" and profile.get("pending_changes"):
                profile["pending_changes"] = None
            elif kind == "MINECRAFT" and profile.get("pending_minecraft"):
                self.links.delete_one({"_id": profile["pending_minecraft"]["uuid"], "owner_id": uid}, session=session)
                profile["pending_minecraft"] = None
            else:
                raise ProfileError("NO_PENDING_REQUEST", "Cette demande n'est plus en attente.", 409)
            self.record(profile, uid, kind + "_CHANGE_CANCELLED")
            self.profiles.replace_one({"_id": uid}, profile, session=session)
        self.bank.transact(execute)
        return self.snapshot(uid)


def endpoint(*, admin=False, server=False):
    def decorate(view):
        @csrf_exempt
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            try:
                if server:
                    if not _has_server_api_key(request):
                        raise ProfileError("AUTH_REQUIRED", "Authentification du serveur requise.", 401)
                else:
                    token = request.headers.get("Authorization", "")
                    if not token.startswith("Bearer "):
                        raise ProfileError("AUTH_REQUIRED", "Connectez-vous avec Google.", 401)
                    try:
                        request.profile_uid = auth.verify_id_token(token[7:])["uid"]
                    except Exception:
                        raise ProfileError("AUTH_REQUIRED", "Votre connexion a expiré. Reconnectez-vous.", 401)
                request.profile_service = Profiles(get_bank())
                if server:
                    # The old API key is also present in browser configurations. It cannot prove game ownership.
                    server_id = request.headers.get("X-Renblood-Link-Server", "")
                    server_key = request.headers.get("X-Renblood-Link-Key", "")
                    trusted = request.profile_service.db.player_registration_servers.find_one({"_id": server_id, "enabled": True})
                    if not trusted or not server_key or len(server_key) > 128 or not secrets.compare_digest(
                            trusted["key_hash"], hashlib.sha256(server_key.encode()).hexdigest()):
                        raise ProfileError("GAME_PROOF_REQUIRED", "L'association doit être confirmée depuis un serveur Minecraft autorisé.", 401)
                if admin:
                    user = request.profile_service.db.players.find_one({"id": request.profile_uid})
                    if not user or user.get("rank") != "Admin":
                        raise ProfileError("FORBIDDEN", "Accès administrateur requis.", 403)
                request.profile_body = {}
                if request.method in {"POST", "PATCH", "PUT"}:
                    if len(request.body) > 16384:
                        raise ProfileError("INVALID_REQUEST", "Requête trop volumineuse.")
                    try:
                        request.profile_body = json.loads(request.body or b"{}")
                    except (ValueError, UnicodeError):
                        raise ProfileError("INVALID_REQUEST", "Le contenu envoyé est invalide.")
                    if not isinstance(request.profile_body, dict):
                        raise ProfileError("INVALID_REQUEST", "Un objet JSON est attendu.")
                return view(request, *args, **kwargs)
            except ProfileError as error:
                return JsonResponse({"code": error.code, "message": str(error), "fields": error.fields}, status=error.status)
            except Exception:
                logger.exception("Character registration request failed")
                return JsonResponse({"code": "SERVICE_UNAVAILABLE", "message": "Votre dossier est temporairement inaccessible. Vos informations enregistrées sont conservées. Réessayez."}, status=503)
        return wrapped
    return decorate


def require_method(request, *methods):
    if request.method not in methods:
        raise ProfileError("METHOD_NOT_ALLOWED", "Méthode non autorisée.", 405)


@endpoint()
def session_view(request):
    require_method(request, "POST")
    service, uid = request.profile_service, request.profile_uid
    service.bootstrap(uid)
    service.prepare_bank(uid)
    return JsonResponse(service.snapshot(uid))


@endpoint()
def profile_view(request):
    require_method(request, "GET", "PATCH")
    service, uid = request.profile_service, request.profile_uid
    service.bootstrap(uid)
    return JsonResponse(service.edit(uid, request.profile_body) if request.method == "PATCH" else service.snapshot(uid))


@endpoint()
def submit_view(request):
    require_method(request, "POST")
    request.profile_service.bootstrap(request.profile_uid)
    return JsonResponse(request.profile_service.submit(request.profile_uid, request.profile_body))


@endpoint()
def code_view(request):
    require_method(request, "POST")
    request.profile_service.bootstrap(request.profile_uid)
    return JsonResponse(request.profile_service.issue_code(request.profile_uid))


@endpoint()
def cancel_view(request):
    require_method(request, "POST")
    request.profile_service.bootstrap(request.profile_uid)
    return JsonResponse(request.profile_service.cancel_request(request.profile_uid, request.profile_body))


@endpoint(server=True)
def confirm_view(request):
    require_method(request, "POST")
    service = request.profile_service
    uuid = request.headers.get("X-Minecraft-UUID", "")
    # Bound guessing cost, without depending on a particular API worker process.
    bucket = f"{uuid}:{int(time.time() // 60)}"
    limit = service.db.player_registration_attempts.find_one_and_update({"_id": bucket},
        {"$inc": {"count": 1}, "$setOnInsert": {"purge_at": datetime.fromtimestamp(time.time() + 3600, timezone.utc)}},
        upsert=True, return_document=ReturnDocument.AFTER)
    if limit["count"] > 10:
        raise ProfileError("TOO_MANY_ATTEMPTS", "Trop de tentatives. Attendez une minute.", 429)
    return JsonResponse(service.confirm_code(request.profile_body.get("code"), uuid, request.profile_body.get("username")))


@endpoint(admin=True)
def settings_view(request):
    require_method(request, "GET", "PUT")
    service = request.profile_service
    settings = service.update_settings(request.profile_body, request.profile_uid) if request.method == "PUT" else service.settings()
    return JsonResponse({"settings": settings, "portrait_options": PORTRAITS})


@endpoint(admin=True)
def queue_view(request):
    require_method(request, "GET")
    query, selected = {}, request.GET.get("status", "REQUESTS")
    if selected == "REQUESTS":
        query["$or"] = [{"status": "PENDING"}, {"pending_changes": {"$ne": None}}, {"pending_minecraft": {"$ne": None}}]
    elif selected in {"DRAFT", "PENDING", "ACTIVE"}:
        query["status"] = selected
    elif selected != "ALL":
        raise ProfileError("INVALID_FILTER", "Filtre inconnu.")
    cursor = request.GET.get("cursor")
    if cursor:
        query["_id"] = {"$gt": cursor}
    results = list(request.profile_service.profiles.find(query).sort("_id", 1).limit(51))
    return JsonResponse({"items": [visible(item) for item in results[:50]],
                         "next_cursor": results[49]["_id"] if len(results) > 50 else None})


@endpoint(admin=True)
def review_view(request, uid):
    require_method(request, "POST")
    return JsonResponse(request.profile_service.review(uid, request.profile_body, request.profile_uid))
