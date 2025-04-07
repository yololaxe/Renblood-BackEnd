from djongo import models

class Action(models.Model):
    _id = models.ObjectIdField()
    action_id = models.IntegerField(unique=True)  # ✅ Champ ID personnalisé
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    mana = models.IntegerField()
    chance = models.IntegerField()

    def __str__(self):
        return self.name

