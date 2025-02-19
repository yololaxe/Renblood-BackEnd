from djongo import models

def default_jobs_experience():
    return {
        "jobs": {}
    }

class Player(models.Model):
    id = models.CharField(primary_key=True, max_length=255)  # ID Firebase
    id_minecraft = models.CharField(max_length=255, unique=True)
    pseudo_minecraft = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    surname = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    rank = models.CharField(max_length=255, default="Citoyen")
    money = models.FloatField(default=0.0)
    divin = models.BooleanField(default=False)

    # ✅ Attributs physiques
    life = models.IntegerField(default=10)
    strength = models.IntegerField(default=1)
    speed = models.IntegerField(default=100)
    reach = models.IntegerField(default=5)
    resistance = models.IntegerField(default=0)
    place = models.IntegerField(default=18)
    haste = models.IntegerField(default=78)
    regeneration = models.IntegerField(default=1)

    # ✅ Traits et Actions
    trait = models.JSONField(default=list)  
    actions = models.JSONField(default=list)

    # ✅ Compétences diverses
    dodge = models.IntegerField(default=2)
    discretion = models.IntegerField(default=3)
    charisma = models.IntegerField(default=1)
    rethoric = models.IntegerField(default=1)
    mana = models.IntegerField(default=100)
    negotiation = models.IntegerField(default=0)
    influence = models.IntegerField(default=1)
    skill = models.IntegerField(default=100)

    # ✅ Nouveau format des expériences
    experiences = models.JSONField(default=default_jobs_experience)

    class Meta:
        db_table = "players"

    def __str__(self):
        return f"{self.pseudo_minecraft} ({self.rank})"
