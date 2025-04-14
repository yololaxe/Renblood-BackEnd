import random
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def roll_dice_20(request):
    user = request.user

    if getattr(user, "rank", "").lower() != "admin":
        return Response({"detail": "Accès refusé. Réservé aux administrateurs."}, status=403)

    result = random.randint(1, 20)

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
