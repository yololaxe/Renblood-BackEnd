# serializers.py

from rest_framework import serializers
from jobs.models.node import Node

class NodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Node
        fields = '__all__'
