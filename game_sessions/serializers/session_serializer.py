# game_sessions/serializers/session_serializer.py

from rest_framework import serializers
from game_sessions.models.session import Session

class SessionSerializer(serializers.ModelSerializer):
    players_count   = serializers.SerializerMethodField()
    futures_count   = serializers.SerializerMethodField()
    players         = serializers.SerializerMethodField()
    futures_players = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = [
            'id',
            'year',
            'season',
            'created_date',
            'session_date',
            'players_count',
            'futures_count',
            'players',
            'futures_players',
        ]

    def get_players(self, session):
        players = list(session.players.all())
        return [{"id": player.id, "name": player.pseudo_minecraft or player.name} for player in players]

    def get_players_count(self, session):
        players_cache = getattr(session, "_prefetched_objects_cache", {}).get("players")
        if players_cache is not None:
            return len(players_cache)
        return session.players.count()

    def get_futures_count(self, session):
        futures_cache = getattr(session, "_prefetched_objects_cache", {}).get("futures")
        if futures_cache is not None:
            return len(futures_cache)
        return session.futures.count()

    def get_futures_players(self, session):
        futures = list(session.futures.all())
        return [future.player.pseudo_minecraft or future.player.name for future in futures]
