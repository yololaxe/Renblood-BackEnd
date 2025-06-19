# jobs/serializers/global_serializer.py
from rest_framework import serializers
from jobs.models.globals import Global

class GlobalSerializer(serializers.ModelSerializer):
    # On mappe le champ `_id` de Djongo sur un champ `id` lisible
    id = serializers.CharField(source="_id", read_only=True)

    class Meta:
        model = Global
        fields = [
            "id", 
            "year", 
            "season", 
            "one_session_state", 
            "future_modif_add_state",
        ]
