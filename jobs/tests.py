from djongo import models

class Job(models.Model):
    _id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255)
    skills = models.JSONField(default=dict, blank=True, null=True)
    recipes_to_learn = models.JSONField(default=list, blank=True, null=True)
    mastery = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "jobs"

    def __str__(self):
        return self.name
