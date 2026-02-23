from djongo import models
from django.utils import timezone

class Npc(models.Model):
    TYPE_CHOICES = [
        ('DECO', 'DECO'),
        ('SHOPKEEPER', 'SHOPKEEPER'),
        ('QUEST', 'QUEST'),
    ]

    # Champs communs
    npc_id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='DECO')
    skin = models.CharField(max_length=255, blank=True, null=True) # Texture path/id
    dialogue = models.JSONField(default=list, blank=True) # List of strings
    tags = models.JSONField(default=list, blank=True) # List of strings
    enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Champs spécifiques DECO
    idle_behavior = models.CharField(max_length=50, blank=True, null=True) # NONE, LOOK_AT_PLAYER, WANDER_SMALL
    ambient_lines = models.JSONField(default=list, blank=True)

    # Champs spécifiques SHOPKEEPER
    shop_id = models.CharField(max_length=255, blank=True, null=True)
    currency = models.CharField(max_length=50, blank=True, null=True)
    open_message = models.CharField(max_length=255, blank=True, null=True)
    trade_category = models.CharField(max_length=255, blank=True, null=True)

    # Champs spécifiques QUEST
    quest_giver = models.BooleanField(default=False)
    quest_validator = models.BooleanField(default=False)
    quest_ids = models.JSONField(default=list, blank=True) # List of quest_ids
    dialogue_by_state = models.JSONField(default=dict, blank=True) # { "available": "...", "in_progress": "...", "completed": "..." }

    class Meta:
        db_table = "npcs"

    def __str__(self):
        return f"{self.npc_id} ({self.type}) - {self.name}"


class NpcSpawn(models.Model):
    SPAWN_RULE_CHOICES = [
        ('STATIC', 'STATIC'),
        ('TIMER', 'TIMER'),
        ('ROAD', 'ROAD'),
        ('ADMIN', 'ADMIN'),
    ]

    spawn_id = models.CharField(max_length=255, primary_key=True)
    npc = models.ForeignKey(Npc, on_delete=models.CASCADE, related_name='spawns')
    
    world = models.CharField(max_length=255, default='world')
    x = models.FloatField()
    y = models.FloatField()
    z = models.FloatField()
    yaw = models.FloatField(default=0.0)
    pitch = models.FloatField(default=0.0)
    
    spawn_rule = models.CharField(max_length=50, choices=SPAWN_RULE_CHOICES, default='STATIC')
    active = models.BooleanField(default=True)
    
    meta = models.JSONField(default=dict, blank=True) # { "routeId": "...", "interval": ... }

    class Meta:
        db_table = "npc_spawns"

    def __str__(self):
        return f"{self.spawn_id} - {self.npc.name} @ {self.x},{self.y},{self.z}"
