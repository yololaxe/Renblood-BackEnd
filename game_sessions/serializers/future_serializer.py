# game_sessions/serializers/future_serializer.py

from rest_framework import serializers
from game_sessions.models.future import Future

# 2) table des valeurs par défaut
TEMPLATE_MAP = {
    Future.TYPE_EXPLORATION: {
        "restrictions": [],
        "cost": 12,
        "description": "Choisir X différents items à récupérer pendant une exploration",
        "chance": 0.78,
        "reward": "X items",
        "question": "Quels items ?"
    },
    Future.TYPE_CONSTRUCTION: {
        "restrictions": [{"metier": "Builder", "level": 3}],
        "cost": 0,  # ou null selon besoin
        "description": "Construction ouverte en OFF avec les matériaux disponibles…",
        "chance": 1.00,
        "reward": "XP Builder",
        "question": "null"
    },
    Future.TYPE_CAISSE_ROYALE: {
        "restrictions": [],
        "cost": 5,
        "description": "Jouer à Destin pour changer de vie",
        "chance": 0.99,
        "reward": "Argent / Trésor / Réputation",
        "question": "null"
    },
    Future.TYPE_REJOINDRE_ARMEE: {
        "restrictions": [],
        "cost": 0,
        "description": "Tirage au sort d’un défi PvP / PvE",
        "chance": 0,
        "reward": "Argent / Trésor / Réputation",
        "question": "null"
    },
    Future.TYPE_MAGASIN: {
        "restrictions": [{"magasin": ""}],
        "cost": 0,
        "description": "Reçoit les clients et réalise des ventes",
        "chance": 0,
        "reward": "Argent / Réputation",
        "question": "Nom du magasin & ID"
    },
    Future.TYPE_TRAVAILLER: {
        "restrictions": [{"lieu_de_travail": ""}],
        "cost": 0,
        "description": "Produit des items suivant le planning",
        "chance": 0,
        "reward": "X items",
        "question": "Quels items ?"
    },
    Future.TYPE_ESPIONNER: {
        "restrictions": [],
        "cost": 0,
        "description": "Espionne une personne ou un bâtiment (+5 discrétion)",
        "chance": 0,
        "reward": "Information",
        "question": "Qui ? / Quel bâtiment ?"
    },
    Future.TYPE_SENTRAINER: {
        "restrictions": [],
        "cost": 0,
        "description": "Entraîne un talent (max 2 par talent)",
        "chance": 0,
        "reward": "Talent +1",
        "question": "Quel talent ?"
    },
}

class FutureSerializer(serializers.ModelSerializer):
    # 1) On force conversion en chaîne (ObjectId → str)
    id      = serializers.ReadOnlyField()
    session = serializers.ReadOnlyField(source="session.id")
    player  = serializers.ReadOnlyField(source="player.id")

    class Meta:
        model = Future
        fields = [
            "id",
            "session",
            "player",
            "type",
            "restrictions",
            "cost",
            "description",
            "chance",
            "reward",
            "question",
            "answer",
        ]
        read_only_fields = [
            "restrictions",
            "cost",
            "description",
            "chance",
            "reward",
            "question",
        ]

    def create(self, validated_data):
        # 2) Injecte les valeurs par défaut du TEMPLATE_MAP
        tpl = TEMPLATE_MAP.get(validated_data["type"], {})
        validated_data.update(tpl)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Si le type change, on réinjecte tout le tpl
        new_type = validated_data.get("type", None)
        if new_type and new_type != instance.type:
            tpl = TEMPLATE_MAP.get(new_type, {})
            # applique chaque champ du template sur l'instance
            for field, value in tpl.items():
                setattr(instance, field, value)
        # puis on laisse DRF mettre à jour les autres champs (type, answer…)
        return super().update(instance, validated_data)