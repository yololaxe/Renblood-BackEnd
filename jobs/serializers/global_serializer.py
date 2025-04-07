from rest_framework import serializers
from jobs.models.globals import Global

class GlobalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Global
        fields = '__all__'
