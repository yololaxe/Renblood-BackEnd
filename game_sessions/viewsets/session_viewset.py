from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from game_sessions.models.session import Session
from game_sessions.serializers.session_serializer import SessionSerializer
from players.models import Player

class SessionViewSet(viewsets.ModelViewSet):
    queryset = Session.objects.all()
    serializer_class = SessionSerializer

    @action(detail=False, methods=['get'], url_path='current')
    def get_current(self, request):
        from jobs.models.globals import Global
        g = Global.objects.first()
        if not g:
            return Response({"error": "Pas de données globales"}, status=status.HTTP_404_NOT_FOUND)
        try:
            s = Session.objects.get(year=g.year, season=g.season)
            return Response(SessionSerializer(s).data, status=status.HTTP_200_OK)
        except Session.DoesNotExist:
            return Response({"detail": "Pas de session"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='add-player')
    def add_player(self, request, pk=None):
        session = self.get_object()
        player_id = request.data.get("player_id")
        if not player_id:
            return Response({"error": "player_id missing"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            player = Player.objects.get(pk=player_id)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=status.HTTP_404_NOT_FOUND)

        session.players.add(player)
        session.save()
        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='remove-player')
    def remove_player(self, request, pk=None):
        session = self.get_object()
        player_id = request.data.get("player_id")
        if not player_id:
            return Response({"error": "player_id missing"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            player = Player.objects.get(pk=player_id)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=status.HTTP_404_NOT_FOUND)

        session.players.remove(player)
        session.save()
        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)
