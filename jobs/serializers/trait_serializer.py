from rest_framework import serializers
from jobs.models.trait import Trait

class TraitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trait
        fields = '__all__'
