from djongo import models

class Global(models.Model):
    _id = models.ObjectIdField()
    year = models.IntegerField(default=334)
    season = models.IntegerField(default=1)

    def __str__(self):
        return f"Year {self.year}, Season {self.season}"

    class Meta:
        db_table = "globals"
