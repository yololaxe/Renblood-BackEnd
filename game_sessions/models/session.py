# game_sessions/models/session.py

from django.db import models
from players.models import Player

class Session(models.Model):
    SEASON_PRINTEMPS = 1
    SEASON_ETE      = 2
    SEASON_AUTOMNE  = 3
    SEASON_HIVER    = 4

    SEASON_CHOICES = [
        (SEASON_PRINTEMPS, "Printemps"),
        (SEASON_ETE,       "Été"),
        (SEASON_AUTOMNE,   "Automne"),
        (SEASON_HIVER,     "Hiver"),
    ]

    year          = models.IntegerField()
    season        = models.IntegerField(choices=SEASON_CHOICES)
    created_date  = models.DateTimeField(auto_now_add=True)
    session_date  = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure de la session programmée"
    )

    # Ancienne relation M2M, inchangée pour l’instant
    players       = models.ManyToManyField(
        Player,
        related_name="sessions",
        blank=True,
        help_text="Joueurs participant à cette session"
    )

    # Nouvelle relation M2M via modèle intermédiaire SessionMoney
    players_money = models.ManyToManyField(
        Player,
        through="game_sessions.SessionMoney",
        related_name="sessions_with_money",
        blank=True,
        help_text="Snapshots de solde des joueurs"
    )

    class Meta:
        ordering = ["-created_date"]

    def __str__(self):
        return (
            f"Session {self.get_season_display()} {self.year} "
            f"créée le {self.created_date:%Y-%m-%d}"
        )
