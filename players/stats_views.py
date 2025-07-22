from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.shortcuts import get_object_or_404

from players.models import Player, CHARACTERISTICS
from jobs.models import Job, Trait


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

        # 1) on récupère tous les bonus 'Admin' existants
        existing: dict[str, list] = {}
        for stat, info in (player.real_charact or {}).items():
            if isinstance(info, dict):
                if info.get("type") == "Admin":
                    existing.setdefault(stat, []).append(info)
            elif isinstance(info, list):
                admins = [b for b in info if b.get("type") == "Admin"]
                if admins:
                    existing.setdefault(stat, []).extend(admins)

        # 2) on calcule les bonus talent_tree
        talent_bonuses = self._extract_talent_tree_bonus(player)
        for stat, bonus_list in talent_bonuses.items():
            existing.setdefault(stat, []).extend(bonus_list)

        # 3) on calcule les bonus traits
        trait_bonuses = self._extract_traits_bonus(player)
        for stat, bonus_list in trait_bonuses.items():
            existing.setdefault(stat, []).extend(bonus_list)

        # 4) on enregistre tout
        player.real_charact = existing
        player.save(update_fields=["real_charact"])
        return Response({"real_charact": existing}, status=200)


    def _extract_talent_tree_bonus(self, player):
        """
        Pour chaque job :
          - on aplatit skills + inter_choice + mastery
          - on somme tous les COMP-<stat>_<val> débloqués
          - on retourne { stat_key: [ { count: total_par_job, type: 'talent_tree_<job>' }, … ] }
        """
        exp_jobs = player.experiences.get("jobs", {}) or {}
        if not exp_jobs:
            return {}

        # on peut precharger tous les Docs en une requête
        job_qs = Job.objects.filter(_id__in=exp_jobs.keys()).values(
            "_id", "skills", "inter_choice", "mastery"
        )
        job_map = {j["_id"]: j for j in job_qs}

        bonuses = {}

        for job_name, job_data in exp_jobs.items():
            prog = job_data.get("progression") or []
            job_doc = job_map.get(job_name)
            if not job_doc:
                continue

            # aplatir
            flat = []
            skills = job_doc.get("skills") or {}
            for fld in ("choice_1", "choice_2", "choice_3"):
                flat.extend(skills.get(fld) or [])
            for cmd in (job_doc.get("inter_choice") or []):
                flat.append({"name": cmd})
            for cmd in (job_doc.get("mastery") or []):
                flat.append({"name": cmd})

            # accumulateur pour CE métier
            accum = {}

            for idx, unlocked in enumerate(prog):
                if not unlocked or idx >= len(flat):
                    continue
                name = flat[idx].get("name", "") if isinstance(flat[idx], dict) else str(flat[idx])
                if not name.startswith("COMP-"):
                    continue
                try:
                    _, rest = name.split("COMP-", 1)
                    stat_key, val_str = rest.split("_", 1)
                    val = int(val_str)
                except ValueError:
                    continue

                # filtre selon votre liste de clés
                if stat_key not in CHARACTERISTICS:
                    continue

                accum[stat_key] = accum.get(stat_key, 0) + val

            # pour chaque stat de ce job, on crée un objet bonus
            for stat_key, total in accum.items():
                bonuses.setdefault(stat_key, []).append({
                    "count": total,
                    "type": f"talent_tree_{job_name}"
                })

        return bonuses

    def _extract_traits_bonus(self, player):
        """
        Extrait pour chaque stat les bonus apportés par les traits du joueur.
        Retourne un dict { stat_key: [ {count, type}, … ] }.
        """
        trait_ids = player.traits or []
        if not trait_ids:
            return {}

        # Charger tous les traits d’un coup
        qs = Trait.objects.filter(id__in=trait_ids).values("id", "bonuses")
        bonuses: dict[str, list] = {}

        for trait in qs:
            for stat_key, bonus_list in (trait["bonuses"] or {}).items():
                if stat_key not in CHARACTERISTICS:
                    continue
                for bonus in bonus_list:
                    # on colle simplement le bonus tel quel,
                    # en préfixant le type pour indiquer la source
                    bonuses.setdefault(stat_key, []).append({
                        "count": bonus.get("count", 0),
                        "type": f"trait_{trait['id']}"
                    })

        return bonuses