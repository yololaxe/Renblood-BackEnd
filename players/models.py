from djongo import models

def default_experiences():
    return {
        "Lumberjack": 0,
        "Artisan": 0,
        "Naval_Architect": 0,
        "Carpenter": 0,
        "Miner": 0,
        "Blacksmith": 0,
        "Glassmaker": 0,
        "Mason": 0,
        "Farmer": 0,
        "Breeder": 0,
        "Fisherman": 0,
        "Innkeeper": 0,
        "Guard": 0,
        "Merchant": 0,
        "Transporter": 0,
        "Explorer": 0,
        "Builder": 0,
        "Bestiary": 0,
        "Politician": 0,
        "Banker": 0,
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

    # ✅ Vérifie que ces champs existent bien
    life = models.IntegerField(default=10)
    strength = models.IntegerField(default=1)
    speed = models.IntegerField(default=100)
    reach = models.IntegerField(default=5)
    resistance = models.IntegerField(default=0)
    place = models.IntegerField(default=18)
    haste = models.IntegerField(default=78)
    regeneration = models.IntegerField(default=1)

    # ✅ Assure-toi que `trait` et `actions` sont bien déclarés
    trait = models.JSONField(default=list)  # Stocke une liste de traits
    actions = models.JSONField(default=list)  # Stocke une liste d'actions

    # ✅ Vérifie la déclaration des capacités
    dodge = models.IntegerField(default=2)
    discretion = models.IntegerField(default=3)
    charisma = models.IntegerField(default=1)
    rethoric = models.IntegerField(default=1)
    mana = models.IntegerField(default=100)
    negotiation = models.IntegerField(default=0)
    influence = models.IntegerField(default=1)
    skill = models.IntegerField(default=100)

    # ✅ Vérifie la déclaration des expériences
    experiences = models.JSONField(default=default_experiences)

    class Meta:
        db_table = "players"

    def __str__(self):
        return f"{self.pseudo_minecraft} ({self.rank})"
