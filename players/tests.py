from django.test import SimpleTestCase

from players.services import (
    calculate_level,
    characteristic_totals,
    merge_real_charact,
    normalize_admin_bonuses,
    recalculate_job_levels,
    set_nested,
)


class PlayerServicesTests(SimpleTestCase):
    def test_calculate_level_uses_thresholds(self):
        self.assertEqual(calculate_level(0), 0)
        self.assertEqual(calculate_level(50), 2)
        self.assertEqual(calculate_level(3000), 15)

    def test_set_nested_creates_missing_levels(self):
        payload = {}
        set_nested(payload, ["jobs", "miner", "xp"], 120)
        self.assertEqual(payload, {"jobs": {"miner": {"xp": 120}}})

    def test_recalculate_job_levels_updates_only_changed_jobs(self):
        experiences = {
            "jobs": {
                "miner": {"xp": 750, "level": 1},
                "farmer": {"xp": 10, "level": 0},
            }
        }

        updated, changed = recalculate_job_levels(experiences)

        self.assertTrue(changed)
        self.assertEqual(updated["jobs"]["miner"]["level"], 10)
        self.assertEqual(updated["jobs"]["farmer"]["level"], 0)
        self.assertEqual(experiences["jobs"]["miner"]["level"], 1)

    def test_normalize_admin_bonuses_keeps_only_admin_entries(self):
        raw = {
            "life": [{"count": 2, "type": "Admin"}, {"count": 4, "type": "Trait"}],
            "mana": {"count": 5, "type": "Admin"},
        }

        normalized = normalize_admin_bonuses(raw)

        self.assertEqual(normalized["life"], [{"count": 2, "type": "Admin"}])
        self.assertEqual(normalized["mana"], [{"count": 5, "type": "Admin"}])

    def test_merge_real_charact_combines_sources(self):
        merged = merge_real_charact(
            {"life": [{"count": 2, "type": "Admin"}]},
            {"life": [{"count": 3, "type": "talent_tree_miner"}]},
            {"mana": [{"count": 1, "type": "trait_1"}]},
        )

        self.assertEqual(len(merged["life"]), 2)
        self.assertEqual(merged["mana"], [{"count": 1, "type": "trait_1"}])

    def test_characteristic_totals_adds_bonus_counts(self):
        class DummyPlayer:
            life = 10
            strength = 1
            speed = 100
            reach = 5
            resistance = 0
            place = 18
            haste = 78
            regeneration = 1
            dodge = 2
            discretion = 3
            charisma = 1
            rethoric = 1
            mana = 100
            negotiation = 0
            influence = 1
            skill = 100

        totals = characteristic_totals(
            DummyPlayer(),
            {"life": [{"count": 3, "type": "Admin"}], "mana": [{"count": 10, "type": "Trait"}]},
        )

        self.assertEqual(totals["life"], 13)
        self.assertEqual(totals["mana"], 110)
        self.assertEqual(totals["strength"], 1)
