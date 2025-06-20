# game_sessions/models/session_money.py

from django.db import models
from players.models import Player
from game_sessions.models.session import Session

class SessionMoney(models.Model):
    """
    Historique du solde de chaque joueur au moment d'une Session.
    """
    session     = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="money_snapshots"
    )
    player      = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="session_money_snapshots"
    )
    money       = models.FloatField(help_text="Solde du joueur au moment de la session")
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("session", "player")
        ordering = ["-captured_at"]

    def __str__(self):
        return f"{self.player.pseudo_minecraft}: {self.money} @ {self.captured_at:%Y-%m-%d %H:%M}"
