from rest_framework import serializers
from game_sessions.models.session import Session

class SessionSerializer(serializers.ModelSerializer):
    players_count   = serializers.IntegerField(source='players.count', read_only=True)
    futures_count   = serializers.IntegerField(source='futures.count', read_only=True)
    players         = serializers.SerializerMethodField()
    futures_players = serializers.SerializerMethodField()

    class Meta:
        model  = Session
        fields = [
            'id', 'year', 'season', 'date',
            'players_count', 'futures_count',
            'players', 'futures_players',
        ]

    def get_players(self, session):
        return [
            {'id': p.id, 'name': p.pseudo_minecraft or p.name}
            for p in session.players.all()
        ]

    def get_futures_players(self, session):
        return [
            f.player.pseudo_minecraft or f.player.name
            for f in session.futures.all()
        ]
