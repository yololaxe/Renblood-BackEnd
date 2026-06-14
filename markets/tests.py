from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from .models import (
    CalculatedMarketPrice, City, CityMarketModifier, MarketEconomyConfig, MarketItemReference,
    MarketTransaction, MarketTypeConfig, MarketWithdrawal, MerchantCounter,
    PriceCalculationRun, TemporaryMarketModifier,
)
from .permissions import HasMinecraftApiKey
from .serializers import (
    AdminCounterModerationSerializer,
    MerchantCounterSerializer, MinecraftCounterItemSerializer, MinecraftCounterSerializer,
    MinecraftReferenceItemSerializer, MinecraftTransactionSerializer,
    MinecraftWithdrawalSerializer,
)
from .services import (
    _bounded_price, _compute_activity_modifier_from_bucket, _decimal,
    _enforce_shop_city_order, _next_calculation_version, _stable_random,
    recalculate_prices, record_transaction, summarize_activity,
)
from .views import (
    AdminCounterDisableView, AdminDashboardView, AdminEconomyActivityView,
    AdminRecalculateView, MinecraftCurrentPricesView,
    MinecraftCounterItemDetailView, MinecraftCounterItemListCreateView,
    MinecraftWithdrawalCreateView, PublicMarketPricesView,
)


class PriceCalculationUnitTests(SimpleTestCase):
    def test_decimal128_is_converted_to_decimal(self):
        from bson.decimal128 import Decimal128

        self.assertEqual(_decimal(Decimal128("1.0500")), Decimal("1.0500"))

    def test_random_modifier_is_stable_and_controlled(self):
        first = _stable_random("v1", "city", "SHOP", "minecraft:bread")
        second = _stable_random("v1", "city", "SHOP", "minecraft:bread")
        self.assertEqual(first, second)
        self.assertGreaterEqual(first, Decimal("0.95"))
        self.assertLessEqual(first, Decimal("1.05"))

    def test_price_is_clamped_to_item_bounds_and_one_iron(self):
        item = MarketItemReference(min_price=1, max_price=100)
        self.assertEqual(_bounded_price(item, Decimal("0.1")), 1)
        self.assertEqual(_bounded_price(item, Decimal("1000")), 100)

    def test_city_market_cannot_be_cheaper_than_shop(self):
        item = MarketItemReference(item_id="minecraft:bread")
        prices = {("SHOP", item.item_id): 12, ("CITY_MARKET", item.item_id): 10}
        _enforce_shop_city_order(prices, [item])
        self.assertEqual(prices[("CITY_MARKET", item.item_id)], 12)

    def test_calculation_version_increments_for_same_day(self):
        from django.utils import timezone

        now = timezone.now()
        prefix = now.strftime("%Y-%m-%d")
        runs = [
            SimpleNamespace(calculation_version=f"{prefix}-001"),
            SimpleNamespace(calculation_version=f"{prefix}-003"),
            SimpleNamespace(calculation_version="legacy-version"),
        ]
        self.assertEqual(_next_calculation_version(now, runs), f"{prefix}-004")

    def test_activity_modifier_is_clamped_and_uses_pressure(self):
        config = MarketEconomyConfig(
            dynamic_economy_enabled=True,
            min_transactions_for_impact=1,
            buy_pressure_weight=Decimal("0.0100"),
            sell_pressure_weight=Decimal("0.0100"),
            max_activity_modifier_up=Decimal("1.1500"),
            max_activity_modifier_down=Decimal("0.8500"),
        )
        bucket = {
            "buy_quantity": 30,
            "sell_quantity": 0,
            "buy_transaction_count": 5,
            "sell_transaction_count": 0,
        }
        self.assertEqual(_compute_activity_modifier_from_bucket(bucket, config), Decimal("1.1500"))

    def test_activity_summary_aggregates_transactions_by_city_and_item(self):
        now = timezone.now()
        city = City(id="city-1", name="Lone", active=True)
        transactions = [
            SimpleNamespace(city=city, city_id=city.id, item_id="minecraft:bread", action="BUY", quantity=4, created_at=now),
            SimpleNamespace(city=city, city_id=city.id, item_id="minecraft:bread", action="SELL", quantity=2, created_at=now),
        ]
        references = [MarketItemReference(item_id="minecraft:bread", category="FOOD", display_name="Pain", reference_price=10)]

        def unordered_side_effect(model):
            mapping = {
                PriceCalculationRun: [],
                MarketItemReference: references,
            }
            if model is MarketTransaction:
                return transactions
            return mapping.get(model, [])

        with patch("markets.services._unordered", side_effect=unordered_side_effect), patch(
            "markets.services.get_economy_config", return_value=MarketEconomyConfig(activity_window_days=7)
        ):
            buckets, _config = summarize_activity()

        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0]["buy_quantity"], 4)
        self.assertEqual(buckets[0]["sell_quantity"], 2)

    def test_recalculate_prices_applies_activity_modifier_when_enabled(self):
        now = timezone.now()
        city = City(id="city-1", name="Lone", active=True)
        item = MarketItemReference(item_id="minecraft:bread", category="FOOD", display_name="Pain", reference_price=100, enabled=True, min_price=1)
        config = MarketTypeConfig(type="SHOP", display_name="Shop", base_modifier=Decimal("1.0000"), tax_rate=Decimal("0.0000"), active=True)
        price_rows = []

        def unordered_side_effect(model):
            mapping = {
                PriceCalculationRun: [],
                MarketItemReference: [item],
                City: [city],
                MarketTypeConfig: [config],
                CityMarketModifier: [],
                TemporaryMarketModifier: [],
            }
            return mapping[model]

        def create_run(**kwargs):
            run = SimpleNamespace(**kwargs)
            run.save = Mock()
            return run

        with patch("markets.services._unordered", side_effect=unordered_side_effect), patch(
            "markets.services._stable_random", return_value=Decimal("1.0000")
        ), patch(
            "markets.services.get_economy_config",
            return_value=MarketEconomyConfig(dynamic_economy_enabled=True, activity_window_days=7),
        ), patch(
            "markets.services.recompute_activity_modifiers",
            return_value={"modifiers": [SimpleNamespace(city_id=city.id, item_id=item.item_id, activity_modifier=Decimal("1.1000"))]},
        ), patch(
            "markets.services._persist_current_prices", side_effect=lambda rows, version: price_rows.extend(rows)
        ), patch(
            "markets.services.PriceCalculationRun.objects.create", side_effect=create_run
        ):
            result = recalculate_prices(triggered_by="test", trigger_source="WEBSITE")

        self.assertEqual(result["activityModifiersApplied"], 1)
        self.assertEqual(price_rows[0]["buy_price"], 110)


class ModelRuleUnitTests(SimpleTestCase):
    def test_reference_max_price_cannot_be_below_min_price(self):
        item = MarketItemReference(min_price=10, max_price=9)
        with self.assertRaises(ValidationError):
            item.clean()

    def test_temporary_modifier_end_must_follow_start(self):
        from django.utils import timezone
        now = timezone.now()
        modifier = TemporaryMarketModifier(starts_at=now, ends_at=now)
        with self.assertRaises(ValidationError):
            modifier.clean()

    def test_player_counter_requires_player_inventory_stock(self):
        serializer = MerchantCounterSerializer(data={
            "name": "Private counter",
            "type": "PLAYER_MARKET",
            "owner_type": "PLAYER",
            "owner_id": "player-1",
            "world": "world",
            "x": 1,
            "y": 2,
            "z": 3,
            "created_by": "player-1",
            "items": [{
                "item_id": "custom:item",
                "display_name": "Custom item",
                "category": "OTHER",
                "stock_mode": "LIMITED",
                "stock_quantity": 1,
            }],
        })
        with patch("rest_framework.validators.qs_exists", return_value=False):
            self.assertFalse(serializer.is_valid())
        self.assertIn("items", serializer.errors)

    def test_disabled_counter_cannot_stay_active(self):
        counter = MerchantCounter(
            name="Flagged counter",
            type="SHOP",
            owner_type="ADMIN",
            world="world",
            x=1,
            y=2,
            z=3,
            created_by="admin",
            active=True,
            moderation_status="DISABLED",
        )
        with self.assertRaises(ValidationError):
            counter.clean()


class MinecraftApiKeyUnitTests(SimpleTestCase):
    @override_settings(API_KEY_RENBLOOD="secret")
    def test_api_key_permission(self):
        request = APIRequestFactory().get("/", HTTP_X_API_KEY="secret")
        self.assertTrue(HasMinecraftApiKey().has_permission(request, None))


class MarketUrlUnitTests(SimpleTestCase):
    def test_public_prices_compatibility_url_resolves(self):
        self.assertEqual(resolve("/markets/public-prices/").url_name, "market-public-prices")

    def test_recalculate_url_resolves(self):
        self.assertEqual(resolve("/markets/recalculate/").url_name, "market-recalculate")

    def test_minecraft_market_urls_resolve(self):
        self.assertEqual(resolve("/minecraft/markets/prices/current/").url_name, "minecraft-market-prices")
        self.assertEqual(resolve("/minecraft/markets/counters/counter-1/").url_name, "minecraft-market-counter-detail")
        self.assertEqual(resolve("/minecraft/markets/reference-items/").url_name, "minecraft-reference-items")
        self.assertEqual(
            resolve("/minecraft/markets/counters/counter-1/items/").url_name,
            "minecraft-counter-items",
        )
        self.assertEqual(
            resolve("/minecraft/markets/counters/counter-1/items/minecraft:bread/").url_name,
            "minecraft-counter-item-detail",
        )
        self.assertEqual(
            resolve("/minecraft/markets/counters/counter-1/transactions/").url_name,
            "minecraft-counter-transactions",
        )
        self.assertEqual(
            resolve("/minecraft/markets/counters/counter-1/withdrawals/").url_name,
            "minecraft-counter-withdrawals",
        )

    def test_withdrawal_urls_resolve(self):
        self.assertEqual(resolve("/markets/withdrawals/").url_name, "market-withdrawals")
        self.assertEqual(
            resolve("/markets/counters/counter-1/withdrawals/").url_name,
            "market-counter-withdrawals",
        )

    def test_moderation_urls_resolve(self):
        self.assertEqual(resolve("/markets/counters/moderation/").url_name, "market-counters-moderation")
        self.assertEqual(resolve("/markets/counters/counter-1/disable/").url_name, "market-counter-disable")
        self.assertEqual(resolve("/markets/counters/counter-1/enable/").url_name, "market-counter-enable")
        self.assertEqual(resolve("/markets/counters/counter-1/flag/").url_name, "market-counter-flag")
        self.assertEqual(resolve("/markets/counters/counter-1/audit/").url_name, "market-counter-audit")

    def test_economy_urls_resolve(self):
        self.assertEqual(resolve("/markets/economy/activity/").url_name, "market-economy-activity")
        self.assertEqual(resolve("/markets/economy/activity-modifiers/").url_name, "market-economy-activity-modifiers")
        self.assertEqual(resolve("/markets/economy/recompute-activity/").url_name, "market-economy-recompute-activity")

    def test_dashboard_uses_djongo_compatible_queries(self):
        from django.utils import timezone

        now = timezone.now()
        datasets = {
            "reference": [SimpleNamespace()],
            "cities": [SimpleNamespace(active=True), SimpleNamespace(active=False)],
            "counters": [SimpleNamespace(active=True), SimpleNamespace(active=True)],
            "transactions": [SimpleNamespace(owner_gain=10), SimpleNamespace(owner_gain=None)],
            "runs": [
                SimpleNamespace(
                    id="failed", status="FAILED", calculation_version="v0",
                    triggered_by="test", trigger_source="SYSTEM",
                    started_at=now, finished_at=now, details=None,
                ),
                SimpleNamespace(
                    id="success", status="SUCCESS", calculation_version="v1",
                    triggered_by="test", trigger_source="SYSTEM",
                    started_at=now, finished_at=now, details=None,
                ),
            ],
        }
        querysets = {
            "reference": SimpleNamespace(order_by=lambda: datasets["reference"]),
            "cities": SimpleNamespace(order_by=lambda: datasets["cities"]),
            "counters": SimpleNamespace(order_by=lambda: datasets["counters"]),
            "transactions": SimpleNamespace(order_by=lambda: datasets["transactions"]),
            "runs": SimpleNamespace(order_by=lambda: datasets["runs"]),
        }
        request = APIRequestFactory().get("/api/markets/dashboard")
        with patch("markets.views.IsRenbloodAdmin.has_permission", return_value=True), patch(
            "markets.views.MarketItemReference.objects.all", return_value=querysets["reference"]
        ), patch(
            "markets.views.City.objects.all", return_value=querysets["cities"]
        ), patch(
            "markets.views.MerchantCounter.objects.all", return_value=querysets["counters"]
        ), patch(
            "markets.views.MarketTransaction.objects.all", return_value=querysets["transactions"]
        ), patch(
            "markets.views.PriceCalculationRun.objects.all", return_value=querysets["runs"]
        ):
            response = AdminDashboardView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activeCities"], 1)
        self.assertEqual(response.data["activeCounters"], 2)
        self.assertEqual(response.data["ownerGains"], 10)
        self.assertEqual(response.data["latestCalculationRun"]["calculation_version"], "v1")

    @override_settings(PUBLIC_MARKET_ITEM_IDS=["minecraft:bread"])
    def test_public_prices_uses_djongo_compatible_queries(self):
        from django.utils import timezone

        city = SimpleNamespace(id="city-1", name="Renblood", active=True)
        price = SimpleNamespace(
            city_id=city.id,
            item_id="minecraft:bread",
            buy_price=12,
            market_type="SHOP",
            calculation_version="version-1",
            calculated_at=timezone.now(),
        )
        run = SimpleNamespace(
            status="SUCCESS",
            calculation_version="version-1",
            started_at=timezone.now(),
            finished_at=timezone.now(),
        )
        request = APIRequestFactory().get("/api/public/market-prices")
        city_queryset = SimpleNamespace(order_by=lambda: [city])
        price_queryset = SimpleNamespace(order_by=lambda: [price])
        run_queryset = SimpleNamespace(order_by=lambda: [run])
        with patch("markets.views.City.objects.all", return_value=city_queryset) as city_all, patch(
            "markets.views.CalculatedMarketPrice.objects.all", return_value=price_queryset
        ) as price_all, patch(
            "markets.views.PriceCalculationRun.objects.all", return_value=run_queryset
        ) as run_all:
            response = PublicMarketPricesView.as_view()(request)

        city_all.assert_called_once_with()
        price_all.assert_called_once_with()
        run_all.assert_called_once_with()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["cities"][0]["prices"][0]["buyPrice"], 12)

    @override_settings(API_KEY_RENBLOOD="secret")
    def test_recalculate_endpoint_returns_requested_summary(self):
        request = APIRequestFactory().post(
            "/markets/recalculate/",
            {"triggeredBy": "test-server"},
            format="json",
            HTTP_X_API_KEY="secret",
        )
        result = {
            "status": "success",
            "calculationVersion": "2026-06-12-001",
            "citiesProcessed": 23,
            "itemsProcessed": 8,
            "marketTypesProcessed": 5,
            "pricesGenerated": 920,
            "calculatedAt": "2026-06-12T10:00:00Z",
            "run": object(),
        }
        with patch("markets.views.recalculate_prices", return_value=result):
            response = AdminRecalculateView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pricesGenerated"], 920)
        self.assertNotIn("run", response.data)


class MinecraftMarketContractTests(SimpleTestCase):
    def counter(self, counter_type="SHOP"):
        return MerchantCounter(
            id="internal-1", counter_id="counter-1", name="Counter", type=counter_type,
            owner_type="ADMIN", world="overworld", x=0, y=64, z=0, created_by="admin",
        )

    def test_counter_serializer_uses_camel_case(self):
        city = City(id="city-1", name="Lone", active=True)
        counter = SimpleNamespace(
            id="internal-1",
            counter_id="counter_lone_bakery_001",
            name="Boulangerie de Lone",
            type="SHOP",
            city=city,
            owner_type="ADMIN",
            owner_name="Administration",
            world="overworld",
            x=0,
            y=64,
            z=0,
            active=True,
            buy_mode_enabled=True,
            sell_mode_enabled=False,
            created_by="admin",
            items=[],
        )
        data = MinecraftCounterSerializer(counter).data

        self.assertEqual(data["counterId"], "counter_lone_bakery_001")
        self.assertEqual(data["cityId"], "city-1")
        self.assertEqual(data["cityName"], "Lone")
        self.assertTrue(data["buyModeEnabled"])
        self.assertNotIn("owner_type", data)

    def test_transaction_serializer_rejects_incoherent_total(self):
        counter = self.counter()
        serializer = MinecraftTransactionSerializer(data={
            "counterId": "counter-1",
            "playerUuid": "player-1",
            "playerName": "Yololaxe",
            "itemId": "minecraft:bread",
            "itemDisplayName": "Pain",
            "action": "BUY",
            "quantity": 4,
            "unitPrice": 58,
            "totalPrice": 200,
            "ownerGain": 232,
        })
        with patch("rest_framework.relations.SlugRelatedField.to_internal_value", return_value=counter):
            self.assertFalse(serializer.is_valid())
        self.assertIn("totalPrice", serializer.errors)

    def test_withdrawal_serializer_uses_camel_case(self):
        withdrawal = MarketWithdrawal(
            id="withdrawal-1",
            counter_id="counter-1",
            owner_uuid="player-1",
            owner_name="Yololaxe",
            amount=232,
            withdrawn_at=timezone.now(),
            source="MINECRAFT",
        )
        data = MinecraftWithdrawalSerializer(withdrawal).data

        self.assertEqual(data["counterId"], "counter-1")
        self.assertEqual(data["ownerUuid"], "player-1")
        self.assertEqual(data["ownerName"], "Yololaxe")
        self.assertNotIn("owner_uuid", data)

    def test_withdrawal_serializer_rejects_counter_id_mismatch(self):
        serializer = MinecraftWithdrawalSerializer(
            data={
                "counterId": "counter-2",
                "ownerUuid": "player-1",
                "ownerName": "Yololaxe",
                "amount": 232,
                "withdrawnAt": timezone.now(),
            },
            context={"counter_id": "counter-1", "request": object()},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("counterId", serializer.errors)

    @override_settings(API_KEY_RENBLOOD="secret")
    def test_current_prices_returns_only_latest_active_enabled_data(self):
        now = timezone.now()
        city = City(id="city-1", name="Lone", active=True)
        inactive_city = City(id="city-2", name="Hidden", active=False)
        item = MarketItemReference(
            id="item-1", item_id="minecraft:bread", display_name="Pain",
            category="FOOD", reference_price=58, enabled=True,
        )
        disabled_item = MarketItemReference(
            id="item-2", item_id="minecraft:hidden", display_name="Hidden",
            category="OTHER", reference_price=1, enabled=False,
        )
        config = MarketTypeConfig(id="type-1", type="SHOP", display_name="Shop", active=True)
        run = PriceCalculationRun(
            id="run-1", status="SUCCESS", calculation_version="2026-06-12-001",
            triggered_by="test", trigger_source="SYSTEM", started_at=now, finished_at=now,
        )
        prices = [
            CalculatedMarketPrice(
                id="price-1", city=city, market_type="SHOP", item_id=item.item_id,
                category="FOOD", calculated_price=58, buy_price=58, sell_price=58,
                calculation_version=run.calculation_version, calculated_at=now,
            ),
            CalculatedMarketPrice(
                id="price-2", city=inactive_city, market_type="SHOP", item_id=item.item_id,
                category="FOOD", calculated_price=58, buy_price=58, sell_price=58,
                calculation_version=run.calculation_version, calculated_at=now,
            ),
            CalculatedMarketPrice(
                id="price-3", city=city, market_type="SHOP", item_id=disabled_item.item_id,
                category="OTHER", calculated_price=1, buy_price=1, sell_price=1,
                calculation_version=run.calculation_version, calculated_at=now,
            ),
        ]
        querysets = {
            City: SimpleNamespace(order_by=lambda: [city, inactive_city]),
            MarketItemReference: SimpleNamespace(order_by=lambda: [item, disabled_item]),
            MarketTypeConfig: SimpleNamespace(order_by=lambda: [config]),
            PriceCalculationRun: SimpleNamespace(order_by=lambda: [run]),
            CalculatedMarketPrice: SimpleNamespace(order_by=lambda: prices),
        }
        request = APIRequestFactory().get(
            "/minecraft/markets/prices/current/", HTTP_X_API_KEY="secret",
        )
        patches = [
            patch.object(model.objects, "all", return_value=queryset)
            for model, queryset in querysets.items()
        ]
        for active_patch in patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

        response = MinecraftCurrentPricesView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["calculationVersion"], "2026-06-12-001")
        self.assertEqual(len(response.data["prices"]), 1)
        self.assertEqual(response.data["prices"][0]["displayName"], "Pain")

    def test_reference_item_serializer_uses_camel_case(self):
        item = MarketItemReference(
            id="item-1", item_id="minecraft:bread", display_name="Pain",
            category="FOOD", reference_price=64, enabled=True,
        )
        data = MinecraftReferenceItemSerializer(item).data
        self.assertEqual(data["itemId"], "minecraft:bread")
        self.assertEqual(data["referencePrice"], 64)
        self.assertNotIn("reference_price", data)

    def test_counter_item_auto_price_requires_reference_item(self):
        serializer = MinecraftCounterItemSerializer(
            data={"itemId": "minecraft:unknown", "displayName": "Unknown", "autoPrice": True},
            context={"counter": self.counter()},
        )
        with patch("markets.serializers.MarketItemReference.objects.filter") as reference_filter:
            reference_filter.return_value.first.return_value = None
            self.assertFalse(serializer.is_valid())
        self.assertIn("itemId", serializer.errors)

    def test_counter_item_manual_price_and_limited_stock_are_required(self):
        serializer = MinecraftCounterItemSerializer(
            data={
                "itemId": "minecraft:bread", "displayName": "Pain",
                "autoPrice": False, "stockMode": "LIMITED",
            },
            context={"counter": self.counter()},
        )
        with patch("markets.serializers.MarketItemReference.objects.filter") as reference_filter:
            reference_filter.return_value.first.return_value = None
            self.assertFalse(serializer.is_valid())
        self.assertIn("manualBuyPrice", serializer.errors)
        self.assertIn("stockQuantity", serializer.errors)

    def test_counter_item_rejects_player_market_and_player_inventory(self):
        serializer = MinecraftCounterItemSerializer(
            data={
                "itemId": "minecraft:bread", "displayName": "Pain",
                "stockMode": "PLAYER_INVENTORY",
            },
            context={"counter": self.counter("PLAYER_MARKET")},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("stockMode", serializer.errors)

    @override_settings(API_KEY_RENBLOOD="secret")
    def test_counter_item_post_rejects_active_duplicate(self):
        counter = self.counter()
        existing = SimpleNamespace(active=True)
        request = APIRequestFactory().post(
            "/minecraft/markets/counters/counter-1/items/",
            {"itemId": "minecraft:bread", "displayName": "Pain"},
            format="json",
            HTTP_X_API_KEY="secret",
        )
        with patch("markets.views.get_object_or_404", return_value=counter), patch(
            "markets.views.MerchantCounterItem.objects.filter",
        ) as item_filter:
            item_filter.return_value.first.return_value = existing
            response = MinecraftCounterItemListCreateView.as_view()(request, counter_id="counter-1")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["itemId"][0], "Cet item existe déjà dans ce comptoir.")

    @override_settings(API_KEY_RENBLOOD="secret")
    def test_counter_item_delete_disables_item(self):
        counter = self.counter()
        item = SimpleNamespace(item_id="minecraft:bread", active=True, save=Mock())
        request = APIRequestFactory().delete(
            "/minecraft/markets/counters/counter-1/items/minecraft:bread/",
            HTTP_X_API_KEY="secret",
        )
        with patch("markets.views.get_object_or_404", side_effect=[counter, item]):
            response = MinecraftCounterItemDetailView.as_view()(
                request, counter_id="counter-1", item_id="minecraft:bread",
            )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(item.active)
        item.save.assert_called_once_with(update_fields=["active", "updated_at"])

    def test_minecraft_withdrawal_create_links_counter_when_found(self):
        counter = self.counter()
        counter.save = Mock()
        serializer = SimpleNamespace(
            validated_data={"owner_uuid": "player-1"},
            save=Mock(return_value=SimpleNamespace(counter_id="counter-1", owner_uuid="player-1", amount=232, withdrawn_at=timezone.now())),
        )
        view = MinecraftWithdrawalCreateView()
        view.kwargs = {"counter_id": "counter-1"}

        with patch("markets.views.MerchantCounter.objects.filter") as counter_filter, patch(
            "markets.views.refresh_counter_risk"
        ):
            counter_filter.return_value.first.return_value = counter
            view.perform_create(serializer)

        serializer.save.assert_called_once_with(counter_id="counter-1", source="MINECRAFT")

    def test_minecraft_withdrawal_create_logs_warning_on_owner_mismatch(self):
        counter = self.counter()
        counter.owner_id = "owner-expected"
        counter.save = Mock()
        serializer = SimpleNamespace(
            validated_data={"owner_uuid": "owner-actual"},
            save=Mock(return_value=SimpleNamespace(counter_id="counter-1", owner_uuid="owner-actual", amount=232, withdrawn_at=timezone.now())),
        )
        view = MinecraftWithdrawalCreateView()
        view.kwargs = {"counter_id": "counter-1"}

        with patch("markets.views.MerchantCounter.objects.filter") as counter_filter, patch(
            "markets.views.logger.warning"
        ) as logger_warning, patch(
            "markets.views.refresh_counter_risk"
        ):
            counter_filter.return_value.first.return_value = counter
            view.perform_create(serializer)

        logger_warning.assert_called_once()

    def test_minecraft_withdrawal_create_keeps_pending_sync_when_counter_missing(self):
        serializer = SimpleNamespace(
            validated_data={"owner_uuid": "player-1"},
            save=Mock(return_value=SimpleNamespace(counter_id="counter-missing", owner_uuid="player-1", amount=232)),
        )
        view = MinecraftWithdrawalCreateView()
        view.kwargs = {"counter_id": "counter-missing"}

        with patch("markets.views.MerchantCounter.objects.filter") as counter_filter:
            counter_filter.return_value.first.return_value = None
            view.perform_create(serializer)

        serializer.save.assert_called_once_with(counter_id="counter-missing", source="MINECRAFT")


class AdminModerationViewTests(SimpleTestCase):
    def test_disable_view_requires_reason_and_sets_disabled_status(self):
        counter = MerchantCounter(
            id="counter-db-1",
            counter_id="counter-1",
            name="Counter",
            type="PLAYER_MARKET",
            owner_type="PLAYER",
            owner_id="player-1",
            owner_name="Player",
            world="world",
            x=1,
            y=2,
            z=3,
            created_by="minecraft-server",
        )
        counter.itemCount = 0
        counter.transactionCount = 0
        counter.ownerGains = 0
        counter.risk_score = None
        request = APIRequestFactory().post(
            "/markets/counters/counter-db-1/disable/",
            {"reason": "Prix abusifs"},
            format="json",
            HTTP_AUTHORIZATION="Bearer token",
            HTTP_X_FIREBASE_UID="admin-1",
        )

        def moderation_side_effect(instance, status_value, performed_by=None, reason=None):
            instance.active = False
            instance.moderation_status = status_value
            instance.moderation_reason = reason
            return instance

        with patch("markets.views.IsRenbloodAdmin.has_permission", return_value=True), patch(
            "markets.views.get_object_or_404", return_value=counter
        ), patch(
            "markets.views.set_counter_moderation", side_effect=moderation_side_effect
        ), patch(
            "markets.views._attach_counter_metrics", return_value=counter
        ):
            response = AdminCounterDisableView.as_view()(request, pk="counter-db-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["moderationStatus"], "DISABLED")
        self.assertFalse(response.data["active"])

    def test_activity_view_returns_rows(self):
        city = City(id="city-1", name="Lone", active=True)
        request = APIRequestFactory().get(
            "/markets/economy/activity/",
            HTTP_AUTHORIZATION="Bearer token",
        )
        rows = [{
            "city": city,
            "item_id": "minecraft:bread",
            "category": "FOOD",
            "buy_quantity": 4,
            "sell_quantity": 1,
            "buy_transaction_count": 2,
            "sell_transaction_count": 1,
            "period_start": timezone.now(),
            "period_end": timezone.now(),
        }]
        with patch("markets.views.IsRenbloodAdmin.has_permission", return_value=True), patch(
            "markets.views.summarize_activity",
            return_value=(rows, MarketEconomyConfig(dynamic_economy_enabled=False, activity_window_days=7)),
        ):
            response = AdminEconomyActivityView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["rows"][0]["itemId"], "minecraft:bread")
