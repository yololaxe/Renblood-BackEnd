import random
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def roll_dice(request):
    """
    Lance le dé en HTTP puis broadcast sur Channels.
    """
    user = request.user
    if getattr(user, "rank", "").lower() != "admin":
        return Response(
            {"detail": "Accès refusé. Réservé aux administrateurs."},
            status=403
        )

    # Bornes + mod du body JSON (défauts 1–20 et mod 0)
    min_val = int(request.data.get("min", 1))
    max_val = int(request.data.get("max", 20))
    mod     = int(request.data.get("mod", 0))

    # Calcul du résultat
    result = random.randint(min_val, max_val) + mod

    # Broadcast Channels
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dice_room",
        {
            "type": "dice_rolled",
            "value": result,
        }
    )

    return Response({"result": result})
