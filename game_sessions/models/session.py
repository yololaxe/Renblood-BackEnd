# sessions/models/session.py
from django.db import models
from players.models import Player  # adapter selon le nom de votre app joueurs

class Session(models.Model):
    SEASON_PRINTEMPS = 1
    SEASON_ETE     = 2
    SEASON_AUTOMNE = 3
    SEASON_HIVER   = 4

    SEASON_CHOICES = [
        (SEASON_PRINTEMPS, "Printemps"),
        (SEASON_ETE,       "Été"),
        (SEASON_AUTOMNE,   "Automne"),
        (SEASON_HIVER,     "Hiver"),
    ]

    year   = models.IntegerField()
    season = models.IntegerField(choices=SEASON_CHOICES)
    date   = models.DateTimeField(auto_now_add=True)

    players = models.ManyToManyField(
        Player,
        related_name="sessions",
        blank=True,
        help_text="Joueurs participant à cette session"
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Session {self.get_season_display()} {self.year} le {self.date:%Y-%m-%d}"
