# jobs/viewsets/dice_viewset.py
import random
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

class DiceViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['post'], url_path='roll')
    def roll(self, request):
        """
        POST /api/jobs/dice/roll/
        Lance le dé et broadcast via Channels.
        """
        user = request.user
        if getattr(user, "rank", "").lower() != "admin":
            return Response(
                {"detail": "Accès refusé. Réservé aux administrateurs."},
                status=status.HTTP_403_FORBIDDEN
            )

        min_val = int(request.data.get("min", 1))
        max_val = int(request.data.get("max", 20))
        mod     = int(request.data.get("mod", 0))

        result = random.randint(min_val, max_val) + mod

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "dice_room",
            {
                "type": "dice_rolled",
                "value": result,
            }
        )

        return Response({"result": result})
