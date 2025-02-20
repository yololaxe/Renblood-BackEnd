from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from .models import Player
import json
from django.shortcuts import get_object_or_404



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
        "trait": player.trait,
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
                divin=data.get("divin", False),
                life=data.get("life", 10),
                strength=data.get("strength", 1),
                speed=data.get("speed", 100),
                reach=data.get("reach", 5),
                resistance=data.get("resistance", 0),
                place=data.get("place", 18),
                haste=data.get("haste", 78),
                regeneration=data.get("regeneration", 1),
                trait=data.get("trait", []),
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

        # 🔥 Vérification du champ à modifier
        if field == "progression":
            if not isinstance(new_value, list) or len(new_value) != 10:
                return JsonResponse({"error": "La progression doit être une liste de 10 booléens"}, status=400)

        elif field in ["xp", "level"]:
            try:
                new_value = int(new_value)  # Conversion en entier
            except ValueError:
                return JsonResponse({"error": f"La valeur pour {field} doit être un entier"}, status=400)

        experiences["jobs"][job_name][field] = new_value
        player.experiences = experiences
        player.save()

        return JsonResponse({"success": f"{field} de {job_name} mis à jour", "new_value": new_value}, status=200)

    except Player.DoesNotExist:
        return JsonResponse({"error": "Joueur non trouvé"}, status=404)