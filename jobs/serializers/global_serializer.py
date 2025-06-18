# jobs/serializers/global_serializer.py
from rest_framework import serializers
from jobs.models.globals import Global

class GlobalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Global
        fields = [
            "id", 
            "year", 
            "season", 
            "one_session_state", 
            "future_modif_add_state",
        ]
