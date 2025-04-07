from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from jobs.models.action import Action
from jobs.serializers.action_serializer import ActionSerializer

class ActionViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['get'], url_path='get')
    def get_actions(self, request):
        """Retourne toutes les actions"""
        actions = Action.objects.all()
        serialized = ActionSerializer(actions, many=True)
        return Response(serialized.data)
