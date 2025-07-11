# backend Django – views.py
import random
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def roll_dice(request):
    user = request.user

    if getattr(user, "rank", "").lower() != "admin":
        return Response(
            {"detail": "Accès refusé. Réservé aux administrateurs."},
            status=403
        )

    data = request.data
    # Récupère les bornes et le mod si fournis, sinon défaut 1–20 et mod 0
    min_val = int(data.get("min", 1))
    max_val = int(data.get("max", 20))
    mod     = int(data.get("mod", 0))

    # Si la valeur est envoyée par le client, on l'utilise
    if "value" in data:
        result = int(data["value"])
    else:
        result = random.randint(min_val, max_val) + mod

    # Broadcast via Channels
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dice_room",
        {
            "type": "dice_rolled",
            "value": result,
        }
    )

    return Response({"result": result})
