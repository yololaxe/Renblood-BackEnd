from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from .models import Player
import json
from django.shortcuts import get_object_or_404
from .models import Player, Licence
from jobs.models import Trait, Action
from players.stats_views import PlayerStatsViewSet
from utils.decorators import admin_required, minecraft_api_key_or_firebase_admin_required




def get_player(request, player_id):
    player = get_object_or_404(Player, id=player_id)

    response_data = {
        "id": player.id,
        "id_minecraft": player.id_minecraft,
        "pseudo_minecraft": player.pseudo_minecraft,
        "name": player.name,
        "surname": player.surname,
        "description": player.description,
        "rank": player.rank,
        "money": player.money,
        "divin": player.divin,
        "life": player.life,
        "strength": player.strength,
        "speed": player.speed,
        "reach": player.reach,
        "resistance": player.resistance,
        "place": player.place,
        "haste": player.haste,
        "regeneration": player.regeneration,
        "dodge": player.dodge,
        "discretion": player.discretion,
        "charisma": player.charisma,
        "rethoric": player.rethoric,
        "mana": player.mana,
        "negotiation": player.negotiation,
        "influence": player.influence,
        "skill": player.skill,

        # Ajout de real_charact
        "real_charact": player.real_charact or {},

        # L’expérience et la progression des métiers
        "experiences": player.experiences,
        "traits": player.traits,
        "actions": player.actions,
    }

    return JsonResponse(response_data)



@csrf_exempt
@admin_required
def delete_player(request, player_id):
    """Supprimer un joueur avec son ID Firebase"""
    if request.method == "DELETE":
        try:
            player = Player.objects.get(id=player_id)
            player.delete()
            return JsonResponse({"message": "Player deleted"}, status=200)
        except ObjectDoesNotExist:
            return JsonResponse({"error": "Player not found"}, status=404)

    return JsonResponse({"error": "Invalid request"}, status=400)


import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Player, CHARACTERISTICS, default_real_charact

@csrf_exempt
@admin_required
def create_player(request):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)

        # ———————— Préparation des JSONFields ————————

        # Experiences jobs
        experiences = data.get("experiences", {})
        if "jobs" not in experiences or not isinstance(experiences["jobs"], dict):
            experiences = {"jobs": {}}

        # real_charact : doit être un dict de listes de {count, type}
        real_charact = data.get("real_charact", None)
        if real_charact is None or not isinstance(real_charact, dict):
            real_charact = default_real_charact()
        else:
            # On peut filtrer et valider sommairement ici si besoin
            # (la validation fine se fait via les validators du modèle)
            filtered = {}
            for key, entries in real_charact.items():
                if key in CHARACTERISTICS and isinstance(entries, list):
                    filtered[key] = [
                        { "count": int(e.get("count", 0)), "type": str(e.get("type", "")) }
                        for e in entries
                        if isinstance(e, dict)
                    ]
            real_charact = filtered

        # ———————— Création du joueur ————————
        player = Player.objects.create(
            id              = data["id"],
            id_minecraft    = data["id_minecraft"],
            pseudo_minecraft= data["pseudo_minecraft"],
            name            = data.get("name", ""),
            surname         = data.get("surname", ""),
            description     = data.get("description", ""),
            rank            = data.get("rank", "Citoyen"),
            money           = float(data.get("money", 0.0)),
            divin           = data.get("divin", "Aucun"),

            # Attributs physiques
            life            = int(data.get("life", 10)),
            strength        = int(data.get("strength", 1)),
            speed           = int(data.get("speed", 100)),
            reach           = int(data.get("reach", 5)),
            resistance      = int(data.get("resistance", 0)),
            place           = int(data.get("place", 18)),
            haste           = int(data.get("haste", 78)),
            regeneration    = int(data.get("regeneration", 1)),

            # Traits et actions
            traits          = data.get("traits", []),
            actions         = data.get("actions", []),

            # Compétences diverses
            dodge           = int(data.get("dodge", 2)),
            discretion      = int(data.get("discretion", 3)),
            charisma        = int(data.get("charisma", 1)),
            rethoric        = int(data.get("rethoric", 1)),
            mana            = int(data.get("mana", 100)),
            negotiation     = int(data.get("negotiation", 0)),
            influence       = int(data.get("influence", 1)),
            skill           = int(data.get("skill", 100)),

            # Discord
            discord_id          = data.get("discord_id"),
            discord_username    = data.get("discord_username"),
            discord_discriminator = data.get("discord_discriminator"),
            discord_avatar      = data.get("discord_avatar"),

            # JSONFields
            experiences     = experiences,
            real_charact    = real_charact,

            patreon=int(data.get("patreon", 0)),  # 👈 NEW
            # -- JSONFields --
        )

        return JsonResponse({
            "message": "Player ajouté avec succès !",
            "player_id": player.id
        }, status=201)

    except KeyError as e:
        return JsonResponse(
            {"error": f"Champ obligatoire manquant : {e.args[0]}"},
            status=400
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def _set_nested(data: dict, keys: list, value):
    """
    Définit value dans data à l'emplacement imbriqué décrit par keys.
    Crée les niveaux intermédiaires si besoin.
    """
    d = data
    for key in keys[:-1]:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        d = d[key]
    d[keys[-1]] = value


@csrf_exempt
@admin_required
def update_player(request, player_id):
    if request.method != "PUT":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Player non trouvé"}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)

    # on va collecter les champs racine qu’on modifie
    fields_to_update = set()

    for field_path, value in data.items():
        if "." in field_path:
            # nested, on ne gère que "experiences"
            root, *rest = field_path.split(".")
            if root != "experiences":
                continue
            current = player.experiences or {}
            _set_nested(current, rest, value)
            # on replace complètement l’attribut experiences
            player.experiences = current
            fields_to_update.add("experiences")
        else:
            if hasattr(player, field_path):
                if field_path == "patreon":
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        return JsonResponse({"error": "patreon invalide (entier requis)"}, status=400)
                    if value < 0 or value > 3:
                        return JsonResponse({"error": "patreon doit être 0, 1, 2 ou 3"}, status=400)
                setattr(player, field_path, value)
                fields_to_update.add(field_path)

    if fields_to_update:
        # Ne sauve QUE les champs qu’on vient de toucher
        player.save(update_fields=list(fields_to_update))

    return JsonResponse(
        {"message": "Player modifié avec succès !", "player_id": player.id},
        status=200
    )



@csrf_exempt
def get_player_jobs(request, player_id):
    """Renvoie uniquement les jobs du joueur avec son expérience et sa progression."""
    try:
        player = Player.objects.get(id=player_id)
        return JsonResponse({"jobs": player.experiences}, safe=False)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur introuvable"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@admin_required
def update_player_job(request, player_id, job_name, field):
    """
    Met à jour un champ spécifique d'un job pour un joueur donné.
    """
    if request.method != "PUT":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        player = Player.objects.get(id=player_id)
        experiences = player.experiences  # Récupère les expériences du joueur

        if "jobs" not in experiences or job_name not in experiences["jobs"]:
            return JsonResponse({"error": f"Aucun métier '{job_name}' trouvé pour ce joueur"}, status=404)

        # ✅ Récupérer la valeur depuis le body JSON de la requête
        try:
            body = json.loads(request.body)
            new_value = body.get("new_value", None)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Format JSON invalide"}, status=400)

        if new_value is None:
            return JsonResponse({"error": "Aucune valeur fournie"}, status=400)

        # 🔥 Vérification et conversion du champ à modifier
        if field == "progression":
            if not isinstance(new_value, list) or not all(isinstance(val, bool) for val in new_value):
                return JsonResponse({"error": "La progression doit être une liste de booléens"}, status=400)

        elif field in ["xp", "level"]:
            try:
                new_value = int(new_value)  # Conversion en entier
            except ValueError:
                return JsonResponse({"error": f"La valeur pour {field} doit être un entier"}, status=400)

        elif field in ["choose_lvl_10"]:
            if not isinstance(new_value, str):
                return JsonResponse({"error": f"La valeur pour {field} doit être une chaîne de caractères"}, status=400)

        elif field == "inter_choice":
            if not isinstance(new_value, list) or not all(isinstance(val, str) for val in new_value):
                return JsonResponse({"error": "Les inter_choice doivent être une liste de chaînes de caractères"}, status=400)

        elif field == "mastery":
            if not isinstance(new_value, list) or not all(isinstance(val, str) for val in new_value):
                return JsonResponse({"error": "La maîtrise doit être une liste de chaînes de caractères"}, status=400)

        else:
            return JsonResponse({"error": f"Champ '{field}' non reconnu"}, status=400)

        # ✅ Mise à jour du joueur
        experiences["jobs"][job_name][field] = new_value
        player.experiences = experiences
        player.save()

        return JsonResponse({
            "success": f"{field} de {job_name} mis à jour",
            "new_value": new_value
        }, status=200)

    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur non trouvé"}, status=404)

    except Exception as e:
        return JsonResponse({"error": f"Erreur serveur : {str(e)}"}, status=500)


def get_players(request, rank):
    if rank.lower() == "admin":
        players_data = Player.objects.values()
    else:
        players_data = Player.objects.values("pseudo_minecraft", "name", "surname", "rank", "skill", "description", "money", "divin","patreon")

    return JsonResponse(list(players_data), safe=False)


@csrf_exempt
@admin_required
def manage_player_traits_actions(request, player_id, category, action):
    player = get_object_or_404(Player, id=player_id)

    if category not in ["trait", "action"]:
        return JsonResponse({"error": "Invalid category. Use 'trait' or 'action'."}, status=400)

    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
        print(f"🔍 Requête reçue : {data}")  # Debug log
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

    print(f"✅ {category.capitalize()} trouvé : {item}")

    item_data = {
        "id": getattr(item, id_field),
        "Name": item.name,
        "Bonus": item.bonus if category == "trait" else None,
        "Description": item.description if category == "action" else None,
        "Mana": item.mana if category == "action" else None,
        "Chance": item.chance if category == "action" else None
    }
    item_data = {k: v for k, v in item_data.items() if v is not None}  # Supprime les valeurs None

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
                    "Chance": new_item.chance if category == "action" else None
                })
                break
    else:
        return JsonResponse({"error": "Invalid action. Use 'add', 'delete', or 'edit'."}, status=400)

    setattr(player, field_name, current_list)
    player.save()

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


LEVEL_THRESHOLDS = [
    (3000, 15),
    (2000, 14),
    (1600, 13),
    (1250, 12),
    (1000, 11),
    (750, 10),
    (600, 9),
    (450, 8),
    (350, 7),
    (270, 6),
    (200, 5),
    (140, 4),
    (90, 3),
    (50, 2),
    (20, 1),
    (0, 0),
]

@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def update_job_level(request, player_id, job_name):
    """
    Met à jour le level d'un métier d'un joueur en fonction de son xp.
    URL example: POST /players/update_job_level/<player_id>/<job_name>/
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur non trouvé"}, status=404)

    experiences = player.experiences or {}
    jobs = experiences.get("jobs", {})
    if job_name not in jobs:
        return JsonResponse({"error": f"Métier '{job_name}' introuvable pour ce joueur"}, status=404)

    xp = jobs[job_name].get("xp", 0)
    # Détermination du niveau en fonction de la grille
    new_level = 0
    for xp_threshold, lvl in LEVEL_THRESHOLDS:
        if xp >= xp_threshold:
            new_level = lvl
            break

    # Mise à jour et sauvegarde
    jobs[job_name]["level"] = new_level
    player.experiences = experiences
    player.save(update_fields=["experiences"])

    return JsonResponse({
        "message": f"Level de '{job_name}' mis à jour",
        "job": job_name,
        "xp": xp,
        "new_level": new_level
    }, status=200)





from django.http       import JsonResponse
from django.shortcuts  import get_object_or_404
from players.models    import Player, CHARACTERISTICS
from players.stats_views import PlayerStatsViewSet  # ← importer votre ViewSet      # ou d’où viennent vos seuils

@admin_required
def player_full_profile(request, player_id):
    """
    GET /players/stats/<player_id>/full_profile/
    Renvoie toutes les données du joueur, avec niveaux métiers et real_charact recalculés.
    """
    player = get_object_or_404(Player, id=player_id)

    # 1️⃣ Recalculer les levels métiers
    experiences = player.experiences or {}
    jobs = experiences.get("jobs", {})
    for job_name, job_data in jobs.items():
        xp = job_data.get("xp", 0)
        new_level = next(
            (lvl for thresh, lvl in LEVEL_THRESHOLDS if xp >= thresh),
            0
        )
        job_data["level"] = new_level
    player.experiences = experiences

    # 2️⃣ Conserver les bonus Admin existants
    raw = player.real_charact or {}
    existing_admin: dict[str, list] = {}
    for stat, info in raw.items():
        if isinstance(info, dict) and info.get("type") == "Admin":
            existing_admin.setdefault(stat, []).append(info)
        elif isinstance(info, list):
            existing_admin.setdefault(stat, []).extend(
                [b for b in info if b.get("type") == "Admin"]
            )

    # 3️⃣ Récupérer les bonus TalentTree et Traits
    ps_vs = PlayerStatsViewSet()
    talent_bonuses = ps_vs._extract_talent_tree_bonus(player)
    trait_bonuses  = ps_vs._extract_traits_bonus(player)

    # 4️⃣ Fusionner Admin + TalentTree + Traits
    real_charact: dict[str, list] = {}
    # d’abord les Admin
    for stat, lst in existing_admin.items():
        real_charact[stat] = lst.copy()
    # puis l’arbre de talents
    for stat, lst in talent_bonuses.items():
        real_charact.setdefault(stat, []).extend(lst)
    # enfin les traits
    for stat, lst in trait_bonuses.items():
        real_charact.setdefault(stat, []).extend(lst)

    player.real_charact = real_charact

    # 5️⃣ Sauvegarde en une seule opération
    player.save(update_fields=["experiences", "real_charact"])

    # 6️⃣ Construire la réponse
    response_data = {
        "id":               player.id,
        "id_minecraft":     player.id_minecraft,
        "pseudo_minecraft": player.pseudo_minecraft,
        "name":             player.name,
        "surname":          player.surname,
        "description":      player.description,
        "rank":             player.rank,
        "money":            player.money,
        "divin":            player.divin,
        # stats de base
        **{ stat: getattr(player, stat) for stat in CHARACTERISTICS },
        # real_charact + expériences + traits + actions
        "real_charact": real_charact,
        "experiences":  player.experiences,
        "traits":       player.traits,
        "actions":      player.actions,
        "patreon": player.patreon,
    }

    return JsonResponse(response_data, status=200)


def get_player_by_minecraft(request, mc_id):
    """
    GET /players/getByMinecraft/<mc_id>/
    Renvoie toutes les données d'un joueur à partir de son id_minecraft.
    """
    player = get_object_or_404(Player, id_minecraft=mc_id)

    # 1️⃣ Conserver les bonus Admin existants
    raw = player.real_charact or {}
    existing_admin: dict[str, list] = {}
    for stat, info in raw.items():
        if isinstance(info, dict) and info.get("type") == "Admin":
            existing_admin.setdefault(stat, []).append(info)
        elif isinstance(info, list):
            existing_admin.setdefault(stat, []).extend(
                [b for b in info if b.get("type") == "Admin"]
            )

    # 2️⃣ Récupérer les bonus TalentTree et Traits
    ps_vs = PlayerStatsViewSet()
    talent_bonuses = ps_vs._extract_talent_tree_bonus(player)
    trait_bonuses  = ps_vs._extract_traits_bonus(player)

    # 3️⃣ Fusionner Admin + TalentTree + Traits
    real_charact = {}
    # d’abord les Admin
    for stat, lst in existing_admin.items():
        real_charact[stat] = lst.copy()
    # puis l’arbre de talents
    for stat, lst in talent_bonuses.items():
        real_charact.setdefault(stat, []).extend(lst)
    # enfin les traits
    for stat, lst in trait_bonuses.items():
        real_charact.setdefault(stat, []).extend(lst)

    response_data = {
        "id": player.id,
        "id_minecraft": player.id_minecraft,
        "pseudo_minecraft": player.pseudo_minecraft,
        "name": player.name,
        "surname": player.surname,
        "description": player.description,
        "rank": player.rank,
        "money": player.money,
        "divin": player.divin,
        "real_charact": real_charact,
        "experiences": player.experiences,
        "traits": player.traits,
        "actions": player.actions,
        "patreon": player.patreon,
    }

    # Calcul des stats combinées (base + bonus)
    for stat in CHARACTERISTICS:
        base_val = getattr(player, stat, 0)
        bonuses = real_charact.get(stat, [])
        bonus_val = 0
        if isinstance(bonuses, list):
            bonus_val = sum(b.get("count", 0) for b in bonuses if isinstance(b, dict))
        response_data[stat] = base_val + bonus_val

    return JsonResponse(response_data)

@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def deposit_player(request, player_id):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        player = Player.objects.get(id_minecraft=player_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur introuvable"}, status=404)

    try:
        data = json.loads(request.body)
        amount = int(data.get("amount", 0))
    except (ValueError, KeyError):
        return JsonResponse({"error": "Montant invalide"}, status=400)

    # on ajoute et on sauve
    player.money += amount
    player.save(update_fields=["money"])

    return JsonResponse({
        "message": "Dépôt reçu",
        "new_balance": player.money
    }, status=200)


@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def withdraw_player(request, player_id):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    # 1) Récupérer le joueur par id_minecraft
    try:
        player = Player.objects.get(id_minecraft=player_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur introuvable"}, status=404)

    # 2) Parse body JSON
    try:
        data      = json.loads(request.body)
        coin_type = int(data.get("coin_type", -1))
        amount    = int(data.get("amount", 0))
    except (ValueError, KeyError, json.JSONDecodeError):
        return JsonResponse({"error": "Payload invalide"}, status=400)

    # 3) Conversion en cuivre selon le type
    PER_IRON   = 1
    PER_BRONZE = 64 * PER_IRON
    PER_SILVER = 64 * PER_BRONZE
    PER_GOLD   = 64 * PER_SILVER
    if   coin_type == 0: total_copper = amount * PER_IRON
    elif coin_type == 1: total_copper = amount * PER_BRONZE
    elif coin_type == 2: total_copper = amount * PER_SILVER
    elif coin_type == 3: total_copper = amount * PER_GOLD
    else:
        return JsonResponse({"error": "Type de pièce invalide"}, status=400)

    # 4) Vérifier le solde
    if player.money < total_copper:
        return JsonResponse({"error": "Solde insuffisant"}, status=400)

    # 5) Déduire et sauvegarder
    player.money -= total_copper
    player.save(update_fields=["money"])

    # 6) Réponse
    return JsonResponse({
        "message": "Retrait effectué",
        "new_balance": player.money
    }, status=200)

@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def manage_job_xp(request, mc_id):
    """
    POST /players/manage_job_xp/<mc_id>/
    Permet d'ajouter, définir ou retirer de l'XP sur un métier d'un joueur.
    Body JSON attendu :
    {
        "action": "add" | "set" | "remove",
        "job": "NomDuMetier",
        "amount": 100
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

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
        return JsonResponse({"error": "Nom du métier manquant"}, status=400)
    
    if action not in ["add", "set", "remove"]:
        return JsonResponse({"error": "Action invalide (add, set, remove)"}, status=400)

    experiences = player.experiences or {}
    jobs = experiences.get("jobs", {})
    
    # Si le job n'existe pas encore, on l'initialise
    if job_name not in jobs:
        jobs[job_name] = {"xp": 0, "level": 0, "progression": [], "choose_lvl_10": "", "inter_choice": [], "mastery": []}

    current_xp = jobs[job_name].get("xp", 0)

    if action == "add":
        new_xp = current_xp + amount
    elif action == "remove":
        new_xp = max(0, current_xp - amount)
    elif action == "set":
        new_xp = max(0, amount)
    
    jobs[job_name]["xp"] = new_xp

    # Recalcul du niveau
    new_level = 0
    for xp_threshold, lvl in LEVEL_THRESHOLDS:
        if new_xp >= xp_threshold:
            new_level = lvl
            break
    
    jobs[job_name]["level"] = new_level
    
    # Sauvegarde
    player.experiences = experiences
    player.save(update_fields=["experiences"])

    return JsonResponse({
        "message": f"XP mis à jour pour {job_name}",
        "job": job_name,
        "old_xp": current_xp,
        "new_xp": new_xp,
        "level": new_level
    }, status=200)

@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def manage_player_licences(request, mc_id):
    """
    POST /players/licences/<mc_id>/
    Permet d'ajouter, supprimer ou lister les licences d'un joueur.
    Body JSON attendu :
    {
        "action": "add" | "remove" | "list",
        "licence_id": 1, # Requis pour remove
        "name": "Nom de la licence", # Requis pour add
        "owner_name": "Nom du proprio", # Requis pour add
        "exploitant_name": "Nom de l'exploitant", # Requis pour add
        "start_date": "Date de début", # Requis pour add
        "end_date": "Date de fin", # Requis pour add
        "details": "Détails", # Optionnel pour add
        "price": 100.0 # Optionnel pour add
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

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
        licences_data = []
        for licence in licences:
            licences_data.append({
                "id": licence.id,
                "name": licence.name,
                "owner_name": licence.owner_name,
                "exploitant_name": licence.exploitant_name,
                "start_date": licence.start_date,
                "end_date": licence.end_date,
                "details": licence.details,
                "price": licence.price
            })
        return JsonResponse({"licences": licences_data}, status=200)

    elif action == "add":
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
            price=price
        )
        return JsonResponse({"message": "Licence ajoutée", "licence_id": licence.id}, status=201)

    elif action == "remove":
        licence_id = data.get("licence_id")
        if not licence_id:
            return JsonResponse({"error": "ID de licence manquant"}, status=400)

        try:
            licence = Licence.objects.get(id=licence_id, player=player)
            licence.delete()
            return JsonResponse({"message": "Licence supprimée"}, status=200)
        except Licence.DoesNotExist:
            return JsonResponse({"error": "Licence introuvable"}, status=404)

    else:
        return JsonResponse({"error": "Action invalide (add, remove, list)"}, status=400)
