import json
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from jobs.models import Action, Trait
from players.models import CHARACTERISTICS, Licence, Player, default_real_charact
from players.services import (
    LEVEL_THRESHOLDS,
    calculate_level,
    characteristic_totals,
    merge_real_charact,
    normalize_admin_bonuses,
    recalculate_job_levels,
    set_nested,
)
from players.stats_views import PlayerStatsViewSet


logger = logging.getLogger(__name__)


def _player_core_payload(player):
    return {
        "id": player.id,
        "id_minecraft": player.id_minecraft,
        "pseudo_minecraft": player.pseudo_minecraft,
        "name": player.name,
        "surname": player.surname,
        "description": player.description,
        "rank": player.rank,
        "money": player.money,
        "divin": player.divin,
        "experiences": player.experiences,
        "traits": player.traits,
        "actions": player.actions,
    }


def _player_full_payload(player, real_charact=None, experiences=None, include_patreon=True):
    payload = _player_core_payload(player)
    payload.update({
        stat: getattr(player, stat)
        for stat in CHARACTERISTICS
    })
    payload["real_charact"] = real_charact if real_charact is not None else (player.real_charact or {})
    payload["experiences"] = experiences if experiences is not None else player.experiences
    if include_patreon:
        payload["patreon"] = player.patreon
    return payload


def _recompute_player_state(player):
    stats_viewset = PlayerStatsViewSet()
    experiences, levels_changed = recalculate_job_levels(player.experiences)
    admin_bonuses = normalize_admin_bonuses(player.real_charact)
    talent_bonuses = stats_viewset._extract_talent_tree_bonus(player)
    trait_bonuses = stats_viewset._extract_traits_bonus(player)
    real_charact = merge_real_charact(admin_bonuses, talent_bonuses, trait_bonuses)
    real_charact_changed = real_charact != (player.real_charact or {})
    return experiences, real_charact, (levels_changed or real_charact_changed)


def get_player(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    return JsonResponse(_player_full_payload(player))


@csrf_exempt
def delete_player(request, player_id):
    if request.method == "DELETE":
        try:
            player = Player.objects.get(id=player_id)
            player.delete()
            return JsonResponse({"message": "Player deleted"}, status=200)
        except ObjectDoesNotExist:
            return JsonResponse({"error": "Player not found"}, status=404)

    return JsonResponse({"error": "Invalid request"}, status=400)


@csrf_exempt
def create_player(request):
    if request.method != "POST":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)

    try:
        data = json.loads(request.body)

        experiences = data.get("experiences", {})
        if "jobs" not in experiences or not isinstance(experiences["jobs"], dict):
            experiences = {"jobs": {}}

        real_charact = data.get("real_charact")
        if real_charact is None or not isinstance(real_charact, dict):
            real_charact = default_real_charact()
        else:
            filtered = {}
            for key, entries in real_charact.items():
                if key in CHARACTERISTICS and isinstance(entries, list):
                    filtered[key] = [
                        {"count": int(entry.get("count", 0)), "type": str(entry.get("type", ""))}
                        for entry in entries
                        if isinstance(entry, dict)
                    ]
            real_charact = filtered

        player = Player.objects.create(
            id=data["id"],
            id_minecraft=data["id_minecraft"],
            pseudo_minecraft=data["pseudo_minecraft"],
            name=data.get("name", ""),
            surname=data.get("surname", ""),
            description=data.get("description", ""),
            rank=data.get("rank", "Citoyen"),
            money=float(data.get("money", 0.0)),
            divin=data.get("divin", "Aucun"),
            life=int(data.get("life", 10)),
            strength=int(data.get("strength", 1)),
            speed=int(data.get("speed", 100)),
            reach=int(data.get("reach", 5)),
            resistance=int(data.get("resistance", 0)),
            place=int(data.get("place", 18)),
            haste=int(data.get("haste", 78)),
            regeneration=int(data.get("regeneration", 1)),
            traits=data.get("traits", []),
            actions=data.get("actions", []),
            dodge=int(data.get("dodge", 2)),
            discretion=int(data.get("discretion", 3)),
            charisma=int(data.get("charisma", 1)),
            rethoric=int(data.get("rethoric", 1)),
            mana=int(data.get("mana", 100)),
            negotiation=int(data.get("negotiation", 0)),
            influence=int(data.get("influence", 1)),
            skill=int(data.get("skill", 100)),
            discord_id=data.get("discord_id"),
            discord_username=data.get("discord_username"),
            discord_discriminator=data.get("discord_discriminator"),
            discord_avatar=data.get("discord_avatar"),
            experiences=experiences,
            real_charact=real_charact,
            patreon=int(data.get("patreon", 0)),
        )

        return JsonResponse({
            "message": "Player ajoute avec succes !",
            "player_id": player.id,
        }, status=201)
    except KeyError as exc:
        return JsonResponse({"error": f"Champ obligatoire manquant : {exc.args[0]}"}, status=400)
    except Exception as exc:
        logger.exception("create_player failed")
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
def update_player(request, player_id):
    if request.method != "PUT":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Player non trouve"}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)

    fields_to_update = set()
    for field_path, value in data.items():
        if "." in field_path:
            root, *rest = field_path.split(".")
            if root != "experiences":
                continue
            current = player.experiences or {}
            set_nested(current, rest, value)
            player.experiences = current
            fields_to_update.add("experiences")
            continue

        if hasattr(player, field_path):
            if field_path == "patreon":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    return JsonResponse({"error": "patreon invalide (entier requis)"}, status=400)
                if value < 0 or value > 3:
                    return JsonResponse({"error": "patreon doit etre 0, 1, 2 ou 3"}, status=400)
            setattr(player, field_path, value)
            fields_to_update.add(field_path)

    if fields_to_update:
        player.save(update_fields=list(fields_to_update))

    return JsonResponse({"message": "Player modifie avec succes !", "player_id": player.id}, status=200)


@csrf_exempt
def get_player_jobs(request, player_id):
    try:
        player = Player.objects.get(id=player_id)
        return JsonResponse({"jobs": player.experiences}, safe=False)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur introuvable"}, status=404)
    except Exception as exc:
        logger.exception("get_player_jobs failed for player_id=%s", player_id)
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
def update_player_job(request, player_id, job_name, field):
    if request.method != "PUT":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)

    try:
        player = Player.objects.get(id=player_id)
        experiences = player.experiences

        if "jobs" not in experiences or job_name not in experiences["jobs"]:
            return JsonResponse({"error": f"Aucun metier '{job_name}' trouve pour ce joueur"}, status=404)

        try:
            body = json.loads(request.body)
            new_value = body.get("new_value")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Format JSON invalide"}, status=400)

        if new_value is None:
            return JsonResponse({"error": "Aucune valeur fournie"}, status=400)

        if field == "progression":
            if not isinstance(new_value, list) or not all(isinstance(value, bool) for value in new_value):
                return JsonResponse({"error": "La progression doit etre une liste de booleens"}, status=400)
        elif field in ["xp", "level"]:
            try:
                new_value = int(new_value)
            except ValueError:
                return JsonResponse({"error": f"La valeur pour {field} doit etre un entier"}, status=400)
        elif field == "choose_lvl_10":
            if not isinstance(new_value, str):
                return JsonResponse({"error": f"La valeur pour {field} doit etre une chaine de caracteres"}, status=400)
        elif field in ["inter_choice", "mastery"]:
            if not isinstance(new_value, list) or not all(isinstance(value, str) for value in new_value):
                return JsonResponse({"error": f"La valeur pour {field} doit etre une liste de chaines"}, status=400)
        else:
            return JsonResponse({"error": f"Champ '{field}' non reconnu"}, status=400)

        experiences["jobs"][job_name][field] = new_value
        player.experiences = experiences
        player.save(update_fields=["experiences"])

        return JsonResponse({"success": f"{field} de {job_name} mis a jour", "new_value": new_value}, status=200)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur non trouve"}, status=404)
    except Exception as exc:
        logger.exception(
            "update_player_job failed for player_id=%s job_name=%s field=%s",
            player_id,
            job_name,
            field,
        )
        return JsonResponse({"error": f"Erreur serveur : {exc}"}, status=500)


def get_players(request, rank):
    if rank.lower() == "admin":
        players_data = Player.objects.values()
    else:
        players_data = Player.objects.values(
            "pseudo_minecraft",
            "name",
            "surname",
            "rank",
            "skill",
            "description",
            "money",
            "divin",
            "patreon",
        )

    return JsonResponse(list(players_data), safe=False)


@csrf_exempt
def manage_player_traits_actions(request, player_id, category, action):
    player = get_object_or_404(Player, id=player_id)

    if category not in ["trait", "action"]:
        return JsonResponse({"error": "Invalid category. Use 'trait' or 'action'."}, status=400)

    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    field_name = "traits" if category == "trait" else "actions"
    id_field = "trait_id" if category == "trait" else "action_id"
    model = Trait if category == "trait" else Action

    item_id = data.get("id") if request.method == "POST" else request.GET.get("id")
    if not item_id:
        return JsonResponse({"error": "Missing 'id' field."}, status=400)

    try:
        item = model.objects.get(**{id_field: int(item_id)})
    except model.DoesNotExist:
        return JsonResponse({"error": f"{category.capitalize()} not found. ID: {item_id}"}, status=404)

    item_data = {
        "id": getattr(item, id_field),
        "Name": item.name,
        "Bonus": item.bonus if category == "trait" else None,
        "Description": item.description if category == "action" else None,
        "Mana": item.mana if category == "action" else None,
        "Chance": item.chance if category == "action" else None,
    }
    item_data = {key: value for key, value in item_data.items() if value is not None}

    current_list = getattr(player, field_name, [])

    if action == "add":
        if any(trait["id"] == int(item_id) for trait in current_list):
            return JsonResponse({"error": f"{category.capitalize()} already exists for this player"}, status=400)
        current_list.append(item_data)
    elif action == "delete":
        current_list = [trait for trait in current_list if trait["id"] != int(item_id)]
    elif action == "edit":
        new_id = data.get("new_id")
        if not new_id:
            return JsonResponse({"error": "Missing 'new_id' field."}, status=400)
        try:
            new_item = model.objects.get(**{id_field: int(new_id)})
        except model.DoesNotExist:
            return JsonResponse({"error": f"New {category.capitalize()} not found. ID: {new_id}"}, status=404)

        for trait in current_list:
            if trait["id"] == int(item_id):
                trait.update({
                    "id": getattr(new_item, id_field),
                    "Name": new_item.name,
                    "Bonus": new_item.bonus if category == "trait" else None,
                    "Description": new_item.description if category == "action" else None,
                    "Mana": new_item.mana if category == "action" else None,
                    "Chance": new_item.chance if category == "action" else None,
                })
                break
    else:
        return JsonResponse({"error": "Invalid action. Use 'add', 'delete', or 'edit'."}, status=400)

    setattr(player, field_name, current_list)
    player.save(update_fields=[field_name])

    return JsonResponse({"message": f"{category.capitalize()} {action}ed successfully", field_name: current_list}, status=200)


def get_me(request, firebase_uid=None):
    if not firebase_uid:
        return JsonResponse({"error": "Firebase UID manquant"}, status=400)

    try:
        player = Player.objects.get(id=firebase_uid)
        return JsonResponse({
            "id": player.id,
            "rank": player.rank,
            "pseudo_minecraft": player.pseudo_minecraft,
        })
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur introuvable"}, status=404)


@csrf_exempt
def update_job_level(request, player_id, job_name):
    if request.method != "POST":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur non trouve"}, status=404)

    experiences = player.experiences or {}
    jobs = experiences.get("jobs", {})
    if job_name not in jobs:
        return JsonResponse({"error": f"Metier '{job_name}' introuvable pour ce joueur"}, status=404)

    xp = jobs[job_name].get("xp", 0)
    new_level = calculate_level(xp)
    jobs[job_name]["level"] = new_level
    player.experiences = experiences
    player.save(update_fields=["experiences"])

    return JsonResponse({
        "message": f"Level de '{job_name}' mis a jour",
        "job": job_name,
        "xp": xp,
        "new_level": new_level,
    }, status=200)


def player_full_profile(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    experiences, real_charact, changed = _recompute_player_state(player)

    if changed:
        player.experiences = experiences
        player.real_charact = real_charact
        player.save(update_fields=["experiences", "real_charact"])
        logger.info("player_full_profile refreshed cached profile for player_id=%s", player_id)

    response_data = _player_full_payload(player, real_charact=real_charact, experiences=experiences)
    return JsonResponse(response_data, status=200)


def get_player_by_minecraft(request, mc_id):
    player = get_object_or_404(Player, id_minecraft=mc_id)
    experiences, real_charact, changed = _recompute_player_state(player)

    if changed:
        player.experiences = experiences
        player.real_charact = real_charact
        player.save(update_fields=["experiences", "real_charact"])
        logger.info("get_player_by_minecraft refreshed cached profile for mc_id=%s", mc_id)

    response_data = _player_core_payload(player)
    response_data["real_charact"] = real_charact
    response_data["experiences"] = experiences
    response_data["patreon"] = player.patreon
    response_data.update(characteristic_totals(player, real_charact))
    return JsonResponse(response_data)


@csrf_exempt
def deposit_player(request, player_id):
    if request.method != "POST":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)

    try:
        player = Player.objects.get(id_minecraft=player_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur introuvable"}, status=404)

    try:
        data = json.loads(request.body)
        amount = int(data.get("amount", 0))
    except (ValueError, KeyError):
        return JsonResponse({"error": "Montant invalide"}, status=400)

    player.money += amount
    player.save(update_fields=["money"])

    return JsonResponse({"message": "Depot recu", "new_balance": player.money}, status=200)


@csrf_exempt
def withdraw_player(request, player_id):
    if request.method != "POST":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)

    try:
        player = Player.objects.get(id_minecraft=player_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur introuvable"}, status=404)

    try:
        data = json.loads(request.body)
        coin_type = int(data.get("coin_type", -1))
        amount = int(data.get("amount", 0))
    except (ValueError, KeyError, json.JSONDecodeError):
        return JsonResponse({"error": "Payload invalide"}, status=400)

    per_iron = 1
    per_bronze = 64 * per_iron
    per_silver = 64 * per_bronze
    per_gold = 64 * per_silver

    if coin_type == 0:
        total_copper = amount * per_iron
    elif coin_type == 1:
        total_copper = amount * per_bronze
    elif coin_type == 2:
        total_copper = amount * per_silver
    elif coin_type == 3:
        total_copper = amount * per_gold
    else:
        return JsonResponse({"error": "Type de piece invalide"}, status=400)

    if player.money < total_copper:
        return JsonResponse({"error": "Solde insuffisant"}, status=400)

    player.money -= total_copper
    player.save(update_fields=["money"])

    return JsonResponse({"message": "Retrait effectue", "new_balance": player.money}, status=200)


@csrf_exempt
def manage_job_xp(request, mc_id):
    if request.method != "POST":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)

    try:
        player = Player.objects.get(id_minecraft=mc_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur introuvable"}, status=404)

    try:
        data = json.loads(request.body)
        action = data.get("action")
        job_name = data.get("job")
        amount = int(data.get("amount", 0))
    except (ValueError, KeyError, json.JSONDecodeError):
        return JsonResponse({"error": "Payload invalide"}, status=400)

    if not job_name:
        return JsonResponse({"error": "Nom du metier manquant"}, status=400)
    if action not in ["add", "set", "remove"]:
        return JsonResponse({"error": "Action invalide (add, set, remove)"}, status=400)

    experiences = player.experiences or {}
    jobs = experiences.get("jobs", {})
    if job_name not in jobs:
        jobs[job_name] = {
            "xp": 0,
            "level": 0,
            "progression": [],
            "choose_lvl_10": "",
            "inter_choice": [],
            "mastery": [],
        }

    current_xp = jobs[job_name].get("xp", 0)
    if action == "add":
        new_xp = current_xp + amount
    elif action == "remove":
        new_xp = max(0, current_xp - amount)
    else:
        new_xp = max(0, amount)

    jobs[job_name]["xp"] = new_xp
    jobs[job_name]["level"] = calculate_level(new_xp)
    player.experiences = experiences
    player.save(update_fields=["experiences"])

    return JsonResponse({
        "message": f"XP mis a jour pour {job_name}",
        "job": job_name,
        "old_xp": current_xp,
        "new_xp": new_xp,
        "level": jobs[job_name]["level"],
    }, status=200)


@csrf_exempt
def manage_player_licences(request, mc_id):
    if request.method != "POST":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)

    try:
        player = Player.objects.get(id_minecraft=mc_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur introuvable"}, status=404)

    try:
        data = json.loads(request.body)
        action = data.get("action")
    except (ValueError, KeyError, json.JSONDecodeError):
        return JsonResponse({"error": "Payload invalide"}, status=400)

    if action == "list":
        licences = player.licences.all()
        licences_data = [
            {
                "id": licence.id,
                "name": licence.name,
                "owner_name": licence.owner_name,
                "exploitant_name": licence.exploitant_name,
                "start_date": licence.start_date,
                "end_date": licence.end_date,
                "details": licence.details,
                "price": licence.price,
            }
            for licence in licences
        ]
        return JsonResponse({"licences": licences_data}, status=200)

    if action == "add":
        name = data.get("name")
        owner_name = data.get("owner_name")
        exploitant_name = data.get("exploitant_name")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        details = data.get("details", "")
        price = float(data.get("price", 0.0))

        if not all([name, owner_name, exploitant_name, start_date, end_date]):
            return JsonResponse({"error": "Champs manquants pour l'ajout de licence"}, status=400)

        licence = Licence.objects.create(
            player=player,
            name=name,
            owner_name=owner_name,
            exploitant_name=exploitant_name,
            start_date=start_date,
            end_date=end_date,
            details=details,
            price=price,
        )
        return JsonResponse({"message": "Licence ajoutee", "licence_id": licence.id}, status=201)

    if action == "remove":
        licence_id = data.get("licence_id")
        if not licence_id:
            return JsonResponse({"error": "ID de licence manquant"}, status=400)

        try:
            licence = Licence.objects.get(id=licence_id, player=player)
            licence.delete()
            return JsonResponse({"message": "Licence supprimee"}, status=200)
        except Licence.DoesNotExist:
            return JsonResponse({"error": "Licence introuvable"}, status=404)

    return JsonResponse({"error": "Action invalide (add, remove, list)"}, status=400)
