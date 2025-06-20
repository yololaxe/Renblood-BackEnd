# jobs/views/global_viewset.py
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
        global_state = Global.objects.first()
        if not global_state:
            return Response({"error": "No global data found."}, status=404)
        global_state.season += 1
        if global_state.season > 4:
            global_state.season = 1
            global_state.year += 1
        global_state.save()
        return Response(GlobalSerializer(global_state).data)

    @action(detail=False, methods=['post'], url_path='prev-season')
    def prev_season(self, request):
        global_state = Global.objects.first()
        if not global_state:
            return Response({"error": "No global data found."}, status=404)
        global_state.season -= 1
        if global_state.season < 1:
            global_state.season = 4
            global_state.year -= 1
        global_state.save()
        return Response(GlobalSerializer(global_state).data)

    @action(detail=False, methods=['get'], url_path='current-season')
    def get_year_and_season(self, request):
        global_state = Global.objects.first()
        if not global_state:
            return Response({"error": "No global data found."}, status=404)
        season_labels = {1: "Printemps", 2: "Été", 3: "Automne", 4: "Hiver"}
        return Response({
            "id": str(global_state.pk),
            "year": global_state.year,
            "season": global_state.season,
            "label": season_labels.get(global_state.season, "Inconnu"),
            "one_session_state": global_state.one_session_state,
            "future_modif_add_state": global_state.future_modif_add_state,
        })

    @action(detail=False, methods=['patch'], url_path='update-flags')
    def update_flags(self, request):
        """
        PATCH /stats/globals/update-flags/
        Body JSON: { "one_session_state": true/false, "future_modif_add_state": true/false }
        """
        global_state = Global.objects.first()
        if not global_state:
            return Response({"error": "No global data found."}, status=404)

        # On applique un partial update via le serializer
        serializer = GlobalSerializer(global_state, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @action(detail=False, methods=['get'], url_path='active-state')
    def get_active_state(self, request):
        """
        GET /stats/sessions/active-state/
        Renvoie uniquement { one_session_state: bool }
        """
        from jobs.models.globals import Global
        g = Global.objects.first()
        return Response(
            {"one_session_state": bool(g and g.one_session_state)},
            status=status.HTTP_200_OK
        )