from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.shortcuts import get_object_or_404

from players.models import Player, CHARACTERISTICS
from jobs.models    import Job
from jobs.models  import Trait   # ← bien depuis l’app traits


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
        real.setdefault(stat, []).append({"count": count, "type": btype})

        player.real_charact = real
        player.save(update_fields=["real_charact"])
        return Response({"real_charact": real}, status=200)

    @action(detail=True, methods=["post"], url_path="initialize_stats_bonus")
    def initialize_stats_bonus(self, request, pk=None):
        """
        Calcule et stocke dans real_charact :
          1) Les bonus 'Admin' déjà présents
          2) Les bonus de talent_tree
          3) Les bonus des traits MongoDB (champ JSONField `bonus`)
        """
        player = self.get_player(pk)

        # 1) Conserver les bonus "Admin"
        existing: dict[str, list] = {}
        for stat, info in (player.real_charact or {}).items():
            if isinstance(info, dict) and info.get("type") == "Admin":
                existing.setdefault(stat, []).append(info)
            elif isinstance(info, list):
                admins = [b for b in info if b.get("type") == "Admin"]
                if admins:
                    existing.setdefault(stat, []).extend(admins)

        # 2) Ajouter les bonus de l'arbre de talents
        for stat, bl in self._extract_talent_tree_bonus(player).items():
            existing.setdefault(stat, []).extend(bl)

        # 3) Ajouter les bonus des traits
        for stat, bl in self._extract_traits_bonus(player).items():
            existing.setdefault(stat, []).extend(bl)

        # 4) Sauvegarder
        player.real_charact = existing
        player.save(update_fields=["real_charact"])
        return Response({"real_charact": existing}, status=200)


    def _extract_talent_tree_bonus(self, player):
        exp_jobs = player.experiences.get("jobs", {}) or {}
        if not exp_jobs:
            return {}

        job_qs = Job.objects.filter(_id__in=exp_jobs.keys()).values(
            "_id", "skills", "inter_choice", "mastery"
        )
        job_map = {j["_id"]: j for j in job_qs}
        bonuses = {}

        for job_name, job_data in exp_jobs.items():
            prog    = job_data.get("progression") or []
            job_doc = job_map.get(job_name)
            if not job_doc:
                continue

            # Aplatir toutes les compétences et commandes
            flat = []
            skills = job_doc.get("skills") or {}
            for fld in ("choice_1", "choice_2", "choice_3"):
                flat.extend(skills.get(fld) or [])
            for cmd in (job_doc.get("inter_choice") or []):
                flat.append({"name": cmd})
            for cmd in (job_doc.get("mastery") or []):
                flat.append({"name": cmd})

            accum = {}
            for idx, unlocked in enumerate(prog):
                if not unlocked or idx >= len(flat):
                    continue
                entry = flat[idx]
                name  = entry.get("name", "") if isinstance(entry, dict) else str(entry)
                if not name.startswith("COMP-"):
                    continue
                try:
                    _, rest      = name.split("COMP-", 1)
                    stat_key, vs = rest.split("_", 1)
                    val          = int(vs)
                except ValueError:
                    continue
                if stat_key not in CHARACTERISTICS:
                    continue
                accum[stat_key] = accum.get(stat_key, 0) + val

            for stat_key, total in accum.items():
                bonuses.setdefault(stat_key, []).append({
                    "count": total,
                    "type":  f"talent_tree_{job_name}"
                })

        return bonuses


    def _extract_traits_bonus(self, player):
        """
        Extrait les bonus définis dans Trait.bonus (JSONField),
        pour chaque entry de player.traits (qui contient des trait_id ou dicts).
        """
        raw = player.traits or []
        # 1) Normaliser en liste d'IDs entiers
        trait_ids = []
        for entry in raw:
            if isinstance(entry, dict):
                # dict peut contenir key 'trait_id'
                if "trait_id" in entry:
                    trait_ids.append(entry["trait_id"])
                elif "id" in entry:
                    trait_ids.append(entry["id"])
            else:
                trait_ids.append(entry)

        if not trait_ids:
            return {}

        # 2) Charger d'un coup : {trait_id, bonus}
        qs = Trait.objects.filter(trait_id__in=trait_ids).values("trait_id", "bonus")

        bonuses: dict[str, list] = {}
        for tr in qs:
            tid  = tr["trait_id"]
            data = tr.get("bonus") or {}
            # bonus: { "mana": 20, "charisma": 1, ... }
            for stat_key, val in data.items():
                if stat_key not in CHARACTERISTICS:
                    continue
                bonuses.setdefault(stat_key, []).append({
                    "count": val,
                    "type":  f"trait_{tid}"
                })

        return bonuses
