from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from jobs.models.globals import Global
from jobs.serializers.global_serializer import GlobalSerializer

class GlobalViewSet(viewsets.ModelViewSet):
    queryset = Global.objects.all()
    serializer_class = GlobalSerializer

    @action(detail=False, methods=['post'], url_path='next-season')
    def next_season(self, request):
        try:
            global_state = Global.objects.first()
            if not global_state:
                return Response({"error": "No global data found."}, status=404)

            global_state.season += 1
            if global_state.season > 4:
                global_state.season = 1
                global_state.year += 1

            global_state.save()
            return Response(GlobalSerializer(global_state).data, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
