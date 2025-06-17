from djongo import models
from django.core.exceptions import ValidationError

CHARACTERISTICS = [
    "life", "strength", "speed", "reach", "resistance",
    "place", "haste", "regeneration", "dodge", "discretion",
    "charisma", "rethoric", "mana", "negotiation", "influence", "skill"
]

def default_jobs_experience():
    return {"jobs": {}}

def default_real_charact():
    return {}

def validate_real_charact(value):
    if not isinstance(value, dict):
        raise ValidationError("real_charact must be a dict")
    for key, entry in value.items():
        if key not in CHARACTERISTICS:
            raise ValidationError(f"Invalid characteristic '{key}'")
        if not isinstance(entry, dict):
            raise ValidationError(f"Entry for '{key}' must be a dict")
        if "count" not in entry or "type" not in entry:
            raise ValidationError(f"Entry for '{key}' must contain 'count' and 'type'")
        if not isinstance(entry["count"], int):
            raise ValidationError(f"'count' for '{key}' must be an integer")
        if not isinstance(entry["type"], str):
            raise ValidationError(f"'type' for '{key}' must be a string")

class Player(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    id_minecraft = models.CharField(max_length=255, unique=True)
    pseudo_minecraft = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    surname = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    rank = models.CharField(max_length=255, default="Citoyen")
    money = models.FloatField(default=0.0)
    divin = models.CharField(max_length=255)

    # Attributs physiques
    life = models.IntegerField(default=10)
    strength = models.IntegerField(default=1)
    speed = models.IntegerField(default=100)
    reach = models.IntegerField(default=5)
    resistance = models.IntegerField(default=0)
    place = models.IntegerField(default=18)
    haste = models.IntegerField(default=78)
    regeneration = models.IntegerField(default=1)

    # Traits et Actions
    traits = models.JSONField(default=list)
    actions = models.JSONField(default=list)

    # Compétences diverses
    dodge = models.IntegerField(default=2)
    discretion = models.IntegerField(default=3)
    charisma = models.IntegerField(default=1)
    rethoric = models.IntegerField(default=1)
    mana = models.IntegerField(default=100)
    negotiation = models.IntegerField(default=0)
    influence = models.IntegerField(default=1)
    skill = models.IntegerField(default=100)

    # Format des expériences
    experiences = models.JSONField(default=default_jobs_experience)

    # Caractéristiques réelles avec validations
    real_charact = models.JSONField(
        default=default_real_charact,
        validators=[validate_real_charact],
        blank=True,
        help_text="JSON des bonus réels, ex. {'life': {'count':5,'type':'TalentTree'}}"
    )

    class Meta:
        db_table = "players"

    def __str__(self):
        return f"{self.pseudo_minecraft} ({self.rank})"
