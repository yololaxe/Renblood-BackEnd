from djongo import models

class Job(models.Model):
    _id = models.CharField(max_length=255, primary_key=True)  # Clé primaire pour identifier le job
    name = models.CharField(max_length=255)
    skills = models.JSONField(default=dict)  # Stocke les compétences sous forme de JSON
    mastery = models.JSONField(default=list)  # Stocke la maîtrise sous forme de liste

    def __str__(self):
        return self.name
    
    class Meta:
        db_table = "jobs"
