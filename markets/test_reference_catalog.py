from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from markets.management.commands.seed_reference_items import seed_reference_items
from markets.models import MarketItemReference
from markets.reference_catalog import REFERENCE_ITEMS


class ReferenceCatalogueTests(SimpleTestCase):
    def test_catalogue_has_100_unique_vanilla_ids_and_valid_unit_prices(self):
        self.assertEqual(len(REFERENCE_ITEMS), 100)
        for item_id, (name, category, price) in REFERENCE_ITEMS.items():
            self.assertRegex(item_id, r"^minecraft:[a-z0-9_]+$")
            self.assertTrue(name.strip())
            self.assertIs(type(price), int)
            self.assertGreater(price, 0)
        self.assertEqual(REFERENCE_ITEMS["minecraft:bread"][2], 64)
        self.assertEqual(REFERENCE_ITEMS["minecraft:iron_ingot"][2], 320)
        self.assertNotEqual(REFERENCE_ITEMS["minecraft:cobblestone"][0],
                            REFERENCE_ITEMS["minecraft:stone_bricks"][0])

    def test_import_preserves_custom_prices_xp_disabled_and_extra_items(self):
        custom = MarketItemReference(item_id="minecraft:bread", display_name="Pain de mon serveur",
                                     category="FOOD", reference_price=777, reference_xp=42, enabled=False)
        extra = MarketItemReference(item_id="medieval_coins:feran_sigil", category="OTHER",
                                    display_name="Blason", reference_price=300)
        storage = [custom, extra]
        before = dict(custom.__dict__)
        def save(item, **kwargs):
            self.assertTrue(kwargs["force_insert"])
            storage.append(item)
        with patch.object(MarketItemReference.objects, "all") as query, \
                patch.object(MarketItemReference, "save", autospec=True, side_effect=save):
            query.return_value.order_by.side_effect = lambda: list(storage)
            first = seed_reference_items()
            second = seed_reference_items()
        self.assertEqual(first["created"], 99)
        self.assertEqual(first["preserved"], 1)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["preserved"], 100)
        self.assertEqual(len(storage), 101)
        self.assertEqual(custom.__dict__, before)
        self.assertIn(extra, storage)

    def test_dry_run_never_writes(self):
        with patch.object(MarketItemReference.objects, "all") as query, \
                patch.object(MarketItemReference, "save") as save:
            query.return_value.order_by.return_value = []
            result = seed_reference_items(dry_run=True)
        save.assert_not_called()
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["missing"], 100)

    def test_invalid_last_row_prevents_partial_import(self):
        broken = dict(REFERENCE_ITEMS)
        broken["minecraft:blaze_rod"] = ("Bâton", "RARE", 0)
        with patch.object(MarketItemReference.objects, "all") as query, \
                patch.object(MarketItemReference, "save") as save, \
                patch("markets.management.commands.seed_reference_items.REFERENCE_ITEMS", broken):
            query.return_value.order_by.return_value = []
            with self.assertRaises(ValidationError):
                seed_reference_items()
        save.assert_not_called()

    def test_unknown_category_prevents_writes(self):
        with patch.object(MarketItemReference.objects, "all") as query, \
                patch.object(MarketItemReference, "save") as save, \
                patch("markets.management.commands.seed_reference_items.REFERENCE_ITEMS",
                      {"minecraft:bread": ("Pain", "NOT_A_CATEGORY", 64)}):
            query.return_value.order_by.return_value = []
            with self.assertRaises(ValueError):
                seed_reference_items()
        save.assert_not_called()
