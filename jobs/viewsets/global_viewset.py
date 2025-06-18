# src/jobs/views/global_viewset.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from jobs.models.globals import Global
from jobs.serializers.global_serializer import GlobalSerializer

class GlobalViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer l'état global du jeu :
    - next-season : passe à la saison suivante (et incrémente l'année si besoin)
    - prev-season : passe à la saison précédente (et décrémente l'année si besoin)
    - current-season : renvoie year, season, label, et les flags one_session_state / future_modif_add_state
    """
    queryset = Global.objects.all()
    serializer_class = GlobalSerializer

    @action(detail=False, methods=['post'], url_path='next-season')
    def next_season(self, request):
        try:
            global_state = Global.objects.first()
            if not global_state:
                return Response({"error": "No global data found."}, status=404)

            # on passe à la saison suivante
            global_state.season += 1
            if global_state.season > 4:
                global_state.season = 1
                global_state.year += 1

            global_state.save()
            return Response(GlobalSerializer(global_state).data, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='prev-season')
    def prev_season(self, request):
        try:
            global_state = Global.objects.first()
            if not global_state:
                return Response({"error": "No global data found."}, status=404)

            # on revient à la saison précédente
            global_state.season -= 1
            if global_state.season < 1:
                global_state.season = 4
                global_state.year -= 1

            global_state.save()
            return Response(GlobalSerializer(global_state).data, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='current-season')
    def get_year_and_season(self, request):
        """
        GET /stats/globals/current-season/
        Retourne l'id (str), l'année courante, le numéro de saison,
        un libellé humain (Printemps, Été, Automne, Hiver),
        ainsi que les flags one_session_state et future_modif_add_state.
        """
        global_state = Global.objects.first()
        if not global_state:
            return Response({"error": "No global data found."}, status=404)

        # Map saison → libellé
        season_labels = {
            1: "Printemps",
            2: "Été",
            3: "Automne",
            4: "Hiver",
        }
        label = season_labels.get(global_state.season, "Inconnu")

        payload = {
            # on caste en str pour JSON
            "id": str(global_state.pk),
            "year": global_state.year,
            "season": global_state.season,
            "label": label,
            "one_session_state": global_state.one_session_state,
            "future_modif_add_state": global_state.future_modif_add_state,
        }
        return Response(payload, status=200)
