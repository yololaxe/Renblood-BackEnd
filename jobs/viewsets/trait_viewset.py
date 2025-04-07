from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from jobs.models.trait import Trait
from jobs.serializers.trait_serializer import TraitSerializer

class TraitViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['get'], url_path='get')
    def get_traits(self, request):
        """Retourne tous les traits"""
        traits = Trait.objects.all()
        serialized = TraitSerializer(traits, many=True)
        return Response(serialized.data)
