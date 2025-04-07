# from djongo import models

# class Job(models.Model):
#     _id = models.CharField(max_length=255, primary_key=True)  # Clé primaire pour identifier le job
#     name = models.CharField(max_length=255)
#     skills = models.JSONField(default=dict)  # Stocke les compétences sous forme de JSON
#     mastery = models.JSONField(default=list)  # Stocke la maîtrise sous forme de liste
#     inter_choice = models.JSONField(default=list)  # Stocke la maîtrise sous forme de liste
    
#     def __str__(self):
#         return self.name
    
#     class Meta:
#         db_table = "jobs"


# class Trait(models.Model):
#     _id = models.ObjectIdField()  # Garde `_id` géré par MongoDB
#     trait_id = models.IntegerField(unique=True)  # ✅ Champ ID personnalisé
#     name = models.CharField(max_length=255, unique=True)
#     bonus = models.JSONField()

#     def __str__(self):
#         return self.name

# class Action(models.Model):
#     _id = models.ObjectIdField()
#     action_id = models.IntegerField(unique=True)  # ✅ Champ ID personnalisé
#     name = models.CharField(max_length=255, unique=True)
#     description = models.TextField()
#     mana = models.IntegerField()
#     chance = models.IntegerField()

#     def __str__(self):
#         return self.name

