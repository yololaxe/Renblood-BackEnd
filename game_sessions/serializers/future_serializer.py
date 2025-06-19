# sessions/serializers/session_future_serializer.py
from rest_framework import serializers
from game_sessions.models.future import Future

class FutureSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Future
        fields = [
            "id",
            "session",
            "player",
            "restrictions",
            "cost",
            "description",
            "reward",
            "question",
            "answer",
        ]
