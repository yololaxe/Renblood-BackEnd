# game_sessions/models/future.py

from django.db import models
from players.models import Player
from game_sessions.models.session import Session

class Future(models.Model):
    TYPE_EXPLORATION     = "exploration"
    TYPE_CONSTRUCTION    = "construction"
    TYPE_CAISSE_ROYALE   = "caisse_royale"
    TYPE_REJOINDRE_ARMEE = "rejoindre_armee"
    TYPE_MAGASIN         = "tenir_magasin"
    TYPE_TRAVAILLER      = "travailler"
    TYPE_ESPIONNER       = "espionner"
    TYPE_SENTRAINER      = "sentrainer"

    TYPE_CHOICES = [
        (TYPE_EXPLORATION,     "Exploration"),
        (TYPE_CONSTRUCTION,    "Construction"),
        (TYPE_CAISSE_ROYALE,   "La caisse royale !"),
        (TYPE_REJOINDRE_ARMEE, "Rejoindre l’armée"),
        (TYPE_MAGASIN,         "Tenir le magasin"),
        (TYPE_TRAVAILLER,      "Travailler"),
        (TYPE_ESPIONNER,       "Espionner"),
        (TYPE_SENTRAINER,      "S’entraîner"),
    ]

    session      = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="futures")
    player       = models.ForeignKey(Player,  on_delete=models.CASCADE, related_name="session_futures")
    type         = models.CharField(max_length=32, choices=TYPE_CHOICES)
    restrictions = models.JSONField(default=list)
    cost         = models.IntegerField()
    description  = models.TextField()
    chance       = models.FloatField(help_text="Probabilité en pourcentage (0.0–1.0)")
    reward       = models.CharField(max_length=255)
    question     = models.CharField(max_length=255)
    answer       = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"Future {self.get_type_display()} par {self.player}"
