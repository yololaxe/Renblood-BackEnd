from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from .models import Player
import json
from django.shortcuts import get_object_or_404
from .models import Player
from jobs.models import Trait, Action

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
        "traits": player.traits,
        "actions": player.actions,
        "dodge": player.dodge,
        "discretion": player.discretion,
        "charisma": player.charisma,
        "rethoric": player.rethoric,
        "mana": player.mana,
        "negotiation": player.negotiation,
        "influence": player.influence,
        "skill": player.skill,
        "experiences": player.experiences  # Directement au bon format
    }

    return JsonResponse(response_data)


@csrf_exempt
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


@csrf_exempt
def create_player(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            # Vérification et formatage des expériences
            experiences = data.get("experiences", {})
            if "jobs" not in experiences:
                experiences = {"jobs": {}}

            player = Player.objects.create(
                id=data["id"],
                id_minecraft=data["id_minecraft"],
                pseudo_minecraft=data["pseudo_minecraft"],
                name=data["name"],
                surname=data["surname"],
                description=data.get("description", ""),
                rank=data.get("rank", "Citoyen"),
                money=data.get("money", 0.0),
                divin=data.get("divin", "Aucun"),
                life=data.get("life", 10),
                strength=data.get("strength", 1),
                speed=data.get("speed", 100),
                reach=data.get("reach", 5),
                resistance=data.get("resistance", 0),
                place=data.get("place", 18),
                haste=data.get("haste", 78),
                regeneration=data.get("regeneration", 1),
                traits=data.get("traits", []),
                actions=data.get("actions", []),
                dodge=data.get("dodge", 2),
                discretion=data.get("discretion", 3),
                charisma=data.get("charisma", 1),
                rethoric=data.get("rethoric", 1),
                mana=data.get("mana", 100),
                negotiation=data.get("negotiation", 0),
                influence=data.get("influence", 1),
                skill=data.get("skill", 100),
                experiences=experiences
            )

            return JsonResponse({"message": "Player ajouté avec succès!", "player_id": player.id}, status=201)

        except KeyError as e:
            return JsonResponse({"error": f"Champ manquant: {str(e)}"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Méthode non autorisée"}, status=405)


@csrf_exempt
def update_player(request, player_id):
    if request.method == "PUT":
        try:
            player = Player.objects.get(id=player_id)
            data = json.loads(request.body)

            # Mise à jour des champs (uniquement si fournis dans le JSON)
            for field in data:
                if hasattr(player, field):
                    setattr(player, field, data[field])

            player.save()
            return JsonResponse({"message": "Player modifié avec succès!", "player_id": player.id}, status=200)

        except Player.DoesNotExist:
            return JsonResponse({"error": "Player non trouvé"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Méthode non autorisée"}, status=405)

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
        players_data = Player.objects.values("pseudo_minecraft", "name", "surname", "rank", "skill", "description", "money", "divin")

    return JsonResponse(list(players_data), safe=False)


@csrf_exempt
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

# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Player  # ou User si c'est le modèle
from django.shortcuts import get_object_or_404

@api_view(['GET'])
def get_me(request):
    uid = request.headers.get('X-Firebase-UID')  # ou en query params/token si tu veux

    if not uid:
        return Response({"error": "UID Firebase manquant."}, status=400)

    player = get_object_or_404(Player, uid=uid)  # adapte selon ton modèle
    data = {
        "id": player.id,
        "email": player.email,
        "rank": player.rank,
        "uid": player.uid,
        # ajoute ce que tu veux
    }

    return Response(data)
