from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bson.decimal128 import Decimal128
from django.test import SimpleTestCase
from django.utils import timezone

from markets.models import (
    CalculatedMarketPrice, City, CityMarketModifier, MarketItemReference,
    MarketType, MarketTypeConfig, PriceCalculationRun, TemporaryMarketModifier,
)
from markets.services import recalculate_prices
from markets.services import _persist_current_prices


class RecalculationServiceUnitTests(SimpleTestCase):
    def test_recalculation_accepts_decimal128_values_from_mongodb(self):
        now = timezone.now()
        city = City(id="city-active", name="Circos", active=True)
        item = MarketItemReference(
            id="item-active",
            item_id="minecraft:bread",
            display_name="Pain",
            category="FOOD",
            reference_price=100,
            min_price=1,
            enabled=True,
        )
        item.reference_price = Decimal128("100")
        config = MarketTypeConfig(
            id="shop", type=MarketType.SHOP, display_name="Boutique", active=True,
        )
        config.base_modifier = Decimal128("1.10")
        config.tax_rate = Decimal128("0.05")
        modifier = CityMarketModifier(
            id="modifier", city=city, category="FOOD", active=True,
        )
        modifier.modifier = Decimal128("0.50")
        run = Mock(status="FAILED")
        persisted = []
        model_data = {
            PriceCalculationRun: [],
            MarketItemReference: [item],
            City: [city],
            MarketTypeConfig: [config],
            CityMarketModifier: [modifier],
            TemporaryMarketModifier: [],
        }

        with patch("markets.services._unordered", side_effect=lambda model: model_data[model]), patch(
            "markets.services.PriceCalculationRun.objects.create", return_value=run,
        ), patch(
            "markets.services._persist_current_prices",
            side_effect=lambda rows, version: persisted.extend(rows),
        ), patch(
            "markets.services._stable_random", return_value=Decimal("1"),
        ), patch(
            "markets.services.timezone.now", return_value=now,
        ):
            result = recalculate_prices("test", "SYSTEM")

        self.assertEqual(result["pricesGenerated"], 1)
        self.assertEqual(persisted[0]["calculated_price"], 58)
        self.assertEqual(run.status, "SUCCESS")

    def test_recalculation_uses_only_active_data_and_enforces_market_order(self):
        now = timezone.now()
        city = City(id="city-active", name="Circos", active=True)
        inactive_city = City(id="city-inactive", name="Hidden", active=False)
        item = MarketItemReference(
            id="item-active",
            item_id="minecraft:bread",
            display_name="Pain",
            category="FOOD",
            reference_price=100,
            min_price=1,
            max_price=60,
            enabled=True,
        )
        disabled_item = MarketItemReference(
            id="item-disabled",
            item_id="minecraft:disabled",
            display_name="Disabled",
            category="FOOD",
            reference_price=100,
            enabled=False,
        )
        shop = MarketTypeConfig(
            id="shop", type=MarketType.SHOP, display_name="Boutique",
            base_modifier=Decimal("1.10"), tax_rate=Decimal("0"), active=True,
        )
        city_market = MarketTypeConfig(
            id="city-market", type=MarketType.CITY_MARKET, display_name="Marché",
            base_modifier=Decimal("0.90"), tax_rate=Decimal("0"), active=True,
        )
        inactive_type = MarketTypeConfig(
            id="inactive-type", type=MarketType.PLAYER_MARKET, display_name="Inactive",
            base_modifier=Decimal("1"), tax_rate=Decimal("0"), active=False,
        )
        modifier = CityMarketModifier(
            id="modifier", city=city, category="FOOD",
            modifier=Decimal("0.50"), active=True,
        )
        run = Mock(status="FAILED")
        persisted = []

        model_data = {
            PriceCalculationRun: [],
            MarketItemReference: [item, disabled_item],
            City: [city, inactive_city],
            MarketTypeConfig: [shop, city_market, inactive_type],
            CityMarketModifier: [modifier],
            TemporaryMarketModifier: [],
        }

        def unordered(model):
            return model_data[model]

        with patch("markets.services._unordered", side_effect=unordered), patch(
            "markets.services.PriceCalculationRun.objects.create", return_value=run,
        ), patch(
            "markets.services._persist_current_prices",
            side_effect=lambda rows, version: persisted.extend(rows),
        ), patch(
            "markets.services._stable_random", return_value=Decimal("1"),
        ), patch(
            "markets.services.timezone.now", return_value=now,
        ):
            result = recalculate_prices("test", "SYSTEM")

        self.assertEqual(result["citiesProcessed"], 1)
        self.assertEqual(result["itemsProcessed"], 1)
        self.assertEqual(result["marketTypesProcessed"], 2)
        self.assertEqual(result["pricesGenerated"], 2)
        self.assertEqual(len(persisted), 2)
        self.assertEqual({price["calculated_price"] for price in persisted}, {55})
        self.assertTrue(all(price["buy_price"] == price["sell_price"] for price in persisted))
        self.assertEqual(run.status, "SUCCESS")

    def test_price_persistence_uses_one_bulk_write_and_removes_old_versions(self):
        collection = Mock()
        database = {
            CalculatedMarketPrice._meta.db_table: collection,
        }
        row = {
            "city_id": "city-1",
            "market_type": "SHOP",
            "item_id": "minecraft:bread",
            "category": "FOOD",
            "calculated_price": 64,
            "buy_price": 64,
            "sell_price": 64,
            "calculated_at": timezone.now(),
        }
        with patch("markets.services.connection.ensure_connection"), patch(
            "markets.services.connection.connection", database,
        ):
            _persist_current_prices([row], "2026-06-12-001")

        collection.bulk_write.assert_called_once()
        operations = collection.bulk_write.call_args.args[0]
        self.assertEqual(len(operations), 1)
        collection.delete_many.assert_called_once_with({
            "calculation_version": {"$ne": "2026-06-12-001"},
        })
