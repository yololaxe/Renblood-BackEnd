from djongo import models

class Player(models.Model):
    id = models.CharField(primary_key=True, max_length=255)  # ID Firebase
    id_minecraft = models.CharField(max_length=255, unique=True)
    pseudo_minecraft = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    surname = models.CharField(max_length=255)
    total_lvl = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    rank = models.CharField(max_length=255, default="Citoyen")
    money = models.FloatField(default=0.0)
    divin = models.BooleanField(default=False)

    class Meta:
        db_table = "players"

    def __str__(self):
        return f"{self.pseudo_minecraft} ({self.rank})"
