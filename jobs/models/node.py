# models.py

from django.db import models

class Node(models.Model):
    id = models.CharField(primary_key=True, max_length=100)
    en_name = models.CharField(max_length=255)
    fr_name = models.CharField(max_length=255)
    en_description = models.TextField(blank=True)
    fr_description = models.TextField(blank=True)
    type = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.id} ({self.type})"
