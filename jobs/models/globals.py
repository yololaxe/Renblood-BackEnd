# src/jobs/models/globals.py
from djongo import models

class Global(models.Model):
    _id = models.ObjectIdField()
    year = models.IntegerField(default=334)
    season = models.IntegerField(default=1)

    # Nouveaux états globaux
    one_session_state = models.BooleanField(default=False)
    future_modif_add_state = models.BooleanField(default=False)

    def __str__(self):
        return f"Year {self.year}, Season {self.season}, OneSession={self.one_session_state}, FutureModifAdd={self.future_modif_add_state}"

    class Meta:
        db_table = "globals"
