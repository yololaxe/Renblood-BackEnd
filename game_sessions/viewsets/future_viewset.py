# game_sessions/viewsets/future_viewset.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from game_sessions.models.future import Future
from game_sessions.models.session import Session
from players.models import Player
from game_sessions.serializers.future_serializer import FutureSerializer

class FutureViewSet(viewsets.ModelViewSet):
    """
    /sessions/futures/
    CRUD sur les futures + endpoint POST /sessions/futures/add-future/
    pour créer en renvoyant 205.
    """
    queryset = Future.objects.all()
    serializer_class = FutureSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        session_id = self.request.query_params.get("session")
        if session_id:
            qs = qs.filter(session__id=session_id)
        return qs

    @action(detail=False, methods=["post"], url_path="add-future")
    def add_future(self, request):
        # 1) Récupère et valide la session et le player
        session_id = request.data.get("session")
        player_id  = request.data.get("player")
        if not session_id or not player_id:
            return Response(
                {"error": "session and player parameters required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        session = get_object_or_404(Session, pk=session_id)
        player  = get_object_or_404(Player,  pk=player_id)

        # 2) Sérialisation
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 3) On passe explicitement session et player
        future = serializer.save(session=session, player=player)

        return Response(
            self.get_serializer(future).data,
            status=status.HTTP_205_RESET_CONTENT
        )




    @action(detail=False, methods=["get"], url_path="my-future")
    def my_future(self, request):
        session_id = request.query_params.get("session")
        player_id  = request.query_params.get("player_id")
        if not session_id or not player_id:
            return Response(
                {"error": "session and player_id parameters required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        session = get_object_or_404(Session, pk=session_id)
        player  = get_object_or_404(Player, pk=player_id)

        try:
            future = Future.objects.get(session=session, player=player)
        except Future.DoesNotExist:
            return Response({"detail": "Pas de future"}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(future)
        return Response(serializer.data, status=status.HTTP_200_OK)


    @action(detail=True, methods=["patch"], url_path="update-future")
    def update_future(self, request, pk=None):
        """
        PATCH /sessions/futures/{id}/update-future/
        Met à jour la réponse de la future.
        """
        future = get_object_or_404(Future, pk=pk)
        # Vérifier que c'est bien le joueur propriétaire
        if future.player.id != request.user.id:
            return Response({"detail": "Non autorisé"}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(future, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False,methods=["get"],url_path="players-with-futures",)
    def players_with_futures(self, request):
        session_id = request.query_params.get("session")
        if not session_id:
            return Response(
                {"error": "Le paramètre session est requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        session = get_object_or_404(Session, pk=session_id)
        players = session.players.all()
        futures = Future.objects.filter(session=session)
        future_map = {f.player_id: f for f in futures}

        out = []
        for p in players:
            player_data = {
                "id": p.id,
                "name": p.name,
                "pseudo_minecraft": getattr(p, "pseudo_minecraft", None),
            }
            f = future_map.get(p.id)
            future_data = FutureSerializer(f).data if f else None
            out.append({
                "player": player_data,
                "future": future_data
            })

        return Response(out, status=status.HTTP_200_OK)