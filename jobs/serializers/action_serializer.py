from rest_framework import serializers
from jobs.models.action import Action

class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = '__all__'
