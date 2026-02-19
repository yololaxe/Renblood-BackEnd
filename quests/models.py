from djongo import models
from django.utils import timezone

class Quest(models.Model):
    CATEGORY_CHOICES = [
        ('Main', 'Main'),
        ('Secondary', 'Secondary'),
        ('Tertiary', 'Tertiary'),
        ('FullRP', 'FullRP'),
        ('SemiRP', 'SemiRP'),
    ]

    TYPE_CHOICES = [
        ('Solo', 'Solo'),
        ('Multi', 'Multi'),
        ('Hybrid', 'Hybrid'),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    questId = models.CharField(max_length=50, primary_key=True)
    parentId = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=255)
    
    prerequisitesAll = models.JSONField(default=list, blank=True) # List of quest_ids
    prerequisitesAny = models.JSONField(default=list, blank=True) # List of quest_ids
    
    npc = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='Solo')
    
    description = models.JSONField(default=dict) # { "fr": "...", "en": "..." }
    
    objectives = models.JSONField(default=list) # List of objectives
    
    xp = models.JSONField(default=dict, blank=True) # { "job": "...", "amount": ... }
    money = models.IntegerField(default=0)
    
    rewards = models.JSONField(default=list, blank=True) # List of { "itemId": "...", "count": ... }
    
    beginText = models.JSONField(default=dict, blank=True) # { "fr": "...", "en": "..." }
    endText = models.JSONField(default=dict, blank=True) # { "fr": "...", "en": "..." }

    class Meta:
        db_table = "quests"

    def __str__(self):
        return f"{self.questId} - {self.name}"


class PlayerQuestState(models.Model):
    STATUS_CHOICES = [
        ('LOCKED', 'LOCKED'),
        ('AVAILABLE', 'AVAILABLE'),
        ('IN_PROGRESS', 'IN_PROGRESS'),
        ('COMPLETED', 'COMPLETED'),
    ]

    _id = models.CharField(max_length=255, primary_key=True) # player_id + ":" + quest_id
    player_id = models.CharField(max_length=255)
    quest_id = models.CharField(max_length=255)
    
    members = models.JSONField(default=list) # List of player_ids
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='LOCKED')
    
    startedAt = models.DateTimeField(null=True, blank=True)
    completedAt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "player_quest_states"
        unique_together = ('player_id', 'quest_id')

    def save(self, *args, **kwargs):
        if not self._id:
            self._id = f"{self.player_id}:{self.quest_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.player_id} - {self.quest_id} ({self.status})"
