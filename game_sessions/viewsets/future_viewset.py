# sessions/viewsets/session_future_viewset.py
from rest_framework import viewsets, permissions
from game_sessions.models.future import Future
from game_sessions.serializers.future_serializer import FutureSerializer

class FutureViewSet(viewsets.ModelViewSet):
    """
    /session-futures/
    CRUD complet sur les propositions de futurs de session.
    """
    queryset         = Future.objects.all()
    serializer_class = FutureSerializer
    permission_classes = [permissions.IsAuthenticated]  # ou IsAdminUser, selon vos règles
