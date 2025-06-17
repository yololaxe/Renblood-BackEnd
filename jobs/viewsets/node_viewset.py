# views.py

from rest_framework import viewsets
from jobs.models.node import Node
from jobs.serializers.node_serializer import NodeSerializer

class NodeViewSet(viewsets.ModelViewSet):
    queryset = Node.objects.all()
    serializer_class = NodeSerializer
