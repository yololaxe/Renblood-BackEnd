from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from .models import Player
import json

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Player

@csrf_exempt  # Désactiver CSRF pour faciliter les tests en local
def create_player(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            # Vérifier si l'ID existe déjà
            if Player.objects.filter(id=data["id"]).exists():
                return JsonResponse({"error": "Player ID already exists"}, status=400)

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
                experiences=data.get("experiences", {})
            )

            return JsonResponse({"message": "Player created", "id": player.id}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except KeyError as e:
            return JsonResponse({"error": f"Missing key: {str(e)}"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)



def get_player(request, player_id):
    try:
        player = Player.objects.get(id=player_id)
        return JsonResponse({
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
            "experiences": player.experiences,
        }, status=200)

    except Player.DoesNotExist:
        return JsonResponse({"error": "Player not found"}, status=404)


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
def update_player(request, player_id):
    """Met à jour les informations d'un joueur avec son ID Firebase"""
    if request.method == "PATCH":
        try:
            player = Player.objects.get(id=player_id)
            data = json.loads(request.body)

            # Mettre à jour uniquement les champs fournis
            for field, value in data.items():
                if hasattr(player, field):
                    setattr(player, field, value)

            player.save()
            return JsonResponse({"message": "Player updated successfully"}, status=200)

        except Player.DoesNotExist:
            return JsonResponse({"error": "Player not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=400)