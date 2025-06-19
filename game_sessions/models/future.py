# sessions/models/session_future.py
from django.db import models
from players.models import Player
from .session import Session

class Future(models.Model):
    session      = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="futures",
        help_text="Session à laquelle cette proposition appartient"
    )
    player       = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="session_futures",
        help_text="Joueur ayant proposé ce futur"
    )
    restrictions = models.JSONField(
        default=list,
        help_text="Liste de dicts {metier: str, level: int}"
    )
    cost         = models.IntegerField(help_text="Coût en points / ressources")
    description  = models.TextField(help_text="Énoncé de la proposition future")
    reward       = models.CharField(max_length=255, help_text="Récompense prévue")
    question     = models.TextField(help_text="Question à poser au joueur")
    answer       = models.TextField(
        blank=True,
        help_text="Réponse du joueur (sera remplie ultérieurement)"
    )

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"Future#{self.pk} par {self.player} (Session {self.session})"
