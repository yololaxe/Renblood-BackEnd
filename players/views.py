from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from .models import Player
import json

@csrf_exempt
def create_player(request):
    """Créer un joueur avec les données envoyées en JSON"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            # Vérifier si le joueur existe déjà
            if Player.objects.filter(id=data["id"]).exists():
                return JsonResponse({"error": "Player already exists"}, status=400)

            player = Player.objects.create(**data)
            return JsonResponse({"message": "Player created", "id": player.id})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request"}, status=400)


def get_player(request, player_id):
    """Récupérer un joueur avec son ID Firebase"""
    if request.method == "GET":
        try:
            player = Player.objects.get(id=player_id)
            player_data = {
                "id": player.id,
                "id_minecraft": player.id_minecraft,
                "pseudo_minecraft": player.pseudo_minecraft,
                "name": player.name,
                "surname": player.surname,
                "total_lvl": player.total_lvl,
                "description": player.description,
                "rank": player.rank,
                "money": player.money,
                "divin": player.divin,
            }
            return JsonResponse(player_data, status=200)
        except ObjectDoesNotExist:
            return JsonResponse({"error": "Player not found"}, status=404)

    return JsonResponse({"error": "Invalid request"}, status=400)

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
