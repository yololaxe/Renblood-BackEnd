from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.db import transaction
from django.shortcuts import get_object_or_404

from players.models import Player, CHARACTERISTICS
from jobs.models import Job


class PlayerStatsViewSet(viewsets.ViewSet):
    """
    Gère les opérations liées aux caractéristiques bonus du joueur.
    """

    def get_player(self, player_id):
        return get_object_or_404(Player, id=player_id)

    @action(detail=True, methods=["post"], url_path="add_bonus")
    def add_bonus(self, request, pk=None):
        stat  = request.data.get("stat")
        count = request.data.get("count")
        btype = request.data.get("type")

        if stat not in CHARACTERISTICS:
            return Response({"error": f"Stat '{stat}' invalide"}, status=400)
        if not isinstance(count, int):
            return Response({"error": "'count' doit être un entier"}, status=400)
        if not isinstance(btype, str):
            return Response({"error": "'type' doit être une chaîne"}, status=400)

        player = self.get_player(pk)
        real = player.real_charact or {}
        real[stat] = {"count": count, "type": btype}

        player.real_charact = real
        player.save(update_fields=["real_charact"])
        return Response({"real_charact": real}, status=200)

    @action(detail=True, methods=["post"], url_path="initialize_stats_bonus")
    def initialize_stats_bonus(self, request, pk=None):
        player = self.get_player(pk)

        # 1) conserve seulement les bonus Admin existants
        existing = {
            stat: info
            for stat, info in (player.real_charact or {}).items()
            if info.get("type") == "Admin"
        }
        # 2) calcule tous les bonus talent_tree d’un coup
        talent_bonuses = self._extract_talent_tree_bonus(player)
        existing.update(talent_bonuses)

        player.real_charact = existing
        player.save(update_fields=["real_charact"])
        return Response({"real_charact": existing}, status=200)

    def _extract_talent_tree_bonus(self, player):
        """
        Parcourt chaque job dans player.experiences.jobs,
        charge en lot tous les Job (_id, skills, inter_choice, mastery),
        puis calcule les COMP-… débloqués.
        """
        exp_jobs = player.experiences.get("jobs", {}) or {}
        job_names = list(exp_jobs.keys())
        if not job_names:
            return {}

        # Charge en batch; on ne prend QUE les champs existants
        job_qs = Job.objects.filter(_id__in=job_names).values(
            "_id", "skills", "inter_choice", "mastery"
        )
        job_map = {j["_id"]: j for j in job_qs}

        bonuses = {}
        for job_name, job_data in exp_jobs.items():
            progression = job_data.get("progression") or []
            job_doc = job_map.get(job_name)
            if not job_doc:
                continue

            # On aplatit choice_1/choice_2/choice_3 depuis skills JSON
            flat = []
            skills = job_doc.get("skills") or {}
            for choice_field in ("choice_1", "choice_2", "choice_3"):
                flat.extend(skills.get(choice_field) or [])

            # On ajoute inter_choice s'il y en a
            for cmd in (job_doc.get("inter_choice") or []):
                flat.append({"name": cmd})

            # Enfin mastery
            for cmd in (job_doc.get("mastery") or []):
                flat.append({"name": cmd})

            # Parcours de progression
            for idx, unlocked in enumerate(progression):
                if not unlocked or idx >= len(flat):
                    continue

                entry = flat[idx]
                name = entry.get("name") if isinstance(entry, dict) else str(entry)
                if not name.startswith("COMP-"):
                    continue

                try:
                    _, rest = name.split("COMP-", 1)
                    stat_key, val_str = rest.split("_", 1)
                    val = int(val_str)
                except ValueError:
                    continue

                if stat_key in CHARACTERISTICS:
                    curr = bonuses.get(stat_key)
                    if curr:
                        curr["count"] += val
                    else:
                        bonuses[stat_key] = {"count": val, "type": "talent_tree"}

        return bonuses
