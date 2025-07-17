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
        POST /stats/dice/roll/
        Lance le dé et broadcast via Channels.
        """
        # On ne filtre plus sur request.user, on se fie à l'API key/global permissions
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

        return Response({"result": result}, status=status.HTTP_200_OK)
