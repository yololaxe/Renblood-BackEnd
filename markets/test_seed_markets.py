from contextlib import ExitStack
from unittest.mock import patch

from django.test import SimpleTestCase

from markets.management.commands.seed_markets import (
    BASE_MODIFIER_CATEGORIES, CATEGORIES, CITIES, CITY_VARIATIONS,
    MARKET_TYPES, REFERENCE_ITEMS, seed_markets,
)
from markets.models import (
    City, CityMarketModifier, MarketCategory, MarketItemReference,
    MarketTypeConfig,
)


SEEDED_MODELS = [
    City, MarketCategory, MarketTypeConfig, MarketItemReference,
    CityMarketModifier,
]


class SeedMarketsUnitTests(SimpleTestCase):
    def test_seed_catalog_matches_requested_data(self):
        self.assertEqual(len(CITIES), 23)
        self.assertEqual(len(CATEGORIES), 14)
        self.assertEqual(len(MARKET_TYPES), 5)
        self.assertEqual(len(REFERENCE_ITEMS), 8)
        self.assertLessEqual(
            float(MARKET_TYPES["SHOP"][1]),
            float(MARKET_TYPES["CITY_MARKET"][1]),
        )
        self.assertTrue(set(BASE_MODIFIER_CATEGORIES).issubset(set(CATEGORIES)))
        for variations in CITY_VARIATIONS.values():
            self.assertTrue(set(variations).issubset(set(CATEGORIES)))

    def test_seed_is_idempotent(self):
        storage = {model: [] for model in SEEDED_MODELS}

        def unordered(model):
            return list(storage[model])

        def creator(model):
            def create(**values):
                instance = model(**values)
                storage[model].append(instance)
                return instance
            return create

        with ExitStack() as stack:
            stack.enter_context(patch(
                "markets.management.commands.seed_markets._unordered",
                side_effect=unordered,
            ))
            for model in SEEDED_MODELS:
                stack.enter_context(patch.object(model.objects, "create", side_effect=creator(model)))
                stack.enter_context(patch.object(model, "save", return_value=None))

            first = seed_markets()
            second = seed_markets()

        expected_modifiers = len(CITIES) * len(BASE_MODIFIER_CATEGORIES) + 2
        self.assertEqual(first["cities_created"], len(CITIES))
        self.assertEqual(first["categories_created"], len(CATEGORIES))
        self.assertEqual(first["types_created"], len(MARKET_TYPES))
        self.assertEqual(first["items_created"], len(REFERENCE_ITEMS))
        self.assertEqual(first["modifiers_created"], expected_modifiers)

        self.assertEqual(second["cities_created"], 0)
        self.assertEqual(second["categories_created"], 0)
        self.assertEqual(second["types_created"], 0)
        self.assertEqual(second["items_created"], 0)
        self.assertEqual(second["modifiers_created"], 0)
        self.assertEqual(second["cities_existing"], len(CITIES))
        self.assertEqual(second["categories_existing"], len(CATEGORIES))
        self.assertEqual(second["types_existing"], len(MARKET_TYPES))
        self.assertEqual(second["items_existing"], len(REFERENCE_ITEMS))
        self.assertEqual(second["modifiers_existing"], expected_modifiers)
