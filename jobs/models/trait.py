from djongo import models

class Trait(models.Model):
    _id = models.ObjectIdField()  # Garde `_id` géré par MongoDB
    trait_id = models.IntegerField(unique=True)  # ✅ Champ ID personnalisé
    name = models.CharField(max_length=255, unique=True)
    bonus = models.JSONField()

    def __str__(self):
        return self.name