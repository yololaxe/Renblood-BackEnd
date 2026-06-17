import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.permissions import IsRenbloodAdmin

from .models import (
    CalculatedMarketPrice, City, CityMarketModifier, MarketActivityModifier,
    MarketEconomyConfig, MarketItemReference, MarketTransaction, MarketType,
    MarketTypeConfig, MarketWithdrawal, MerchantCounter, MerchantCounterItem,
    ModerationStatus, PriceCalculationRun,
)
from .permissions import HasMinecraftApiKey
from .serializers import (
    AdminCounterAuditSerializer, AdminCounterModerationSerializer,
    CalculatedMarketPriceSerializer, CityMarketModifierSerializer, CitySerializer,
    CounterModerationActionSerializer, MarketActivityModifierSerializer,
    MarketEconomyConfigSerializer, MarketItemReferenceSerializer, MarketTransactionSerializer, MarketWithdrawalSerializer,
    MerchantCounterSerializer,
    MinecraftCounterItemSerializer, MinecraftCounterSerializer,
    MinecraftReferenceItemSerializer, MinecraftTransactionSerializer,
    MinecraftWithdrawalSerializer,
    MinecraftXpReferenceSerializer,
    PriceCalculationRunSerializer,
    RecomputeActivitySerializer,
)
from .services import (
    compute_counter_risk, get_economy_config, recalculate_prices,
    recompute_activity_modifiers, refresh_counter_risk, set_counter_moderation,
    summarize_activity,
)


logger = logging.getLogger(__name__)


def _filter(queryset, request, allowed):
    for field in allowed:
        value = request.query_params.get(field)
        if value not in (None, ""):
            queryset = queryset.filter(**{field: value})
    return queryset


def _request_actor(request):
    return request.headers.get("X-Firebase-Uid") or request.headers.get("X-Admin-Id") or "admin"


@csrf_exempt
def minecraft_admin_audit(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    logger.info(
        "Minecraft admin audit source=%s minecraft_uuid=%s command=%s",
        payload.get("source"),
        payload.get("minecraft_uuid"),
        payload.get("command"),
    )
    return JsonResponse({"ok": True}, status=201)


def _apply_counter_moderation_filters(counters, request):
    query = request.query_params
    owner_name = (query.get("ownerName") or "").strip().lower()
    city_filter = (query.get("city") or "").strip().lower()
    moderation_status = query.get("moderationStatus")
    active = query.get("active")
    counter_type = query.get("type")
    player_only = query.get("playerOnly")
    created_at_from = query.get("createdAtFrom")
    created_at_to = query.get("createdAtTo")
    last_tx_from = query.get("lastTransactionAtFrom")
    last_tx_to = query.get("lastTransactionAtTo")

    filtered = []
    for counter in counters:
        if counter_type and counter.type != counter_type:
            continue
        if moderation_status and counter.moderation_status != moderation_status:
            continue
        if active is not None and active != "":
            wanted = active.lower() == "true"
            if bool(counter.active) != wanted:
                continue
        if player_only and player_only.lower() == "true" and counter.type != MarketType.PLAYER_MARKET:
            continue
        if owner_name and owner_name not in (counter.owner_name or "").lower():
            continue
        city_name = (counter.city.name if counter.city else "")
        city_id = counter.city_id or ""
        if city_filter and city_filter not in city_name.lower() and city_filter != city_id.lower():
            continue
        if created_at_from and counter.created_at.isoformat() < created_at_from:
            continue
        if created_at_to and counter.created_at.isoformat() > created_at_to:
            continue
        if last_tx_from and (not counter.last_transaction_at or counter.last_transaction_at.isoformat() < last_tx_from):
            continue
        if last_tx_to and (not counter.last_transaction_at or counter.last_transaction_at.isoformat() > last_tx_to):
            continue
        filtered.append(counter)
    return filtered


def _attach_counter_metrics(counter, items, transactions):
    counter.itemCount = len(items)
    counter.transactionCount = len(transactions)
    counter.ownerGains = sum(transaction.owner_gain or 0 for transaction in transactions)
    counter.risk_score, counter.riskIndicators = compute_counter_risk(counter, items=items, transactions=transactions)
    return counter


class AdminDashboardView(APIView):
    permission_classes = [IsRenbloodAdmin]

    def get(self, request):
        reference_items = list(MarketItemReference.objects.all().order_by())
        cities = list(City.objects.all().order_by())
        counters = list(MerchantCounter.objects.all().order_by())
        transactions = list(MarketTransaction.objects.all().order_by())
        successful_runs = [
            run for run in PriceCalculationRun.objects.all().order_by()
            if run.status == "SUCCESS"
        ]
        latest = max(
            successful_runs,
            key=lambda run: run.finished_at or run.started_at,
            default=None,
        )
        return Response({
            "referenceItems": len(reference_items),
            "activeCities": sum(1 for city in cities if city.active),
            "activeCounters": sum(1 for counter in counters if counter.active),
            "transactions": len(transactions),
            "ownerGains": sum(transaction.owner_gain or 0 for transaction in transactions),
            "latestCalculationRun": PriceCalculationRunSerializer(latest).data if latest else None,
        })


class AdminRecalculateView(APIView):
    permission_classes = [IsRenbloodAdmin | HasMinecraftApiKey]

    def post(self, request):
        from_minecraft = HasMinecraftApiKey().has_permission(request, self)
        result = recalculate_prices(
            triggered_by=request.data.get("triggeredBy", "minecraft-server" if from_minecraft else "website-admin"),
            trigger_source="MINECRAFT_COMMAND" if from_minecraft else "WEBSITE",
        )
        result.pop("run", None)
        return Response(result, status=status.HTTP_200_OK)


class AdminReferenceItemListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = MarketItemReferenceSerializer
    queryset = MarketItemReference.objects.all()

    def perform_create(self, serializer):
        serializer.save()
        recalculate_prices(triggered_by=_request_actor(self.request), trigger_source="WEBSITE")


class AdminReferenceItemDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = MarketItemReferenceSerializer
    queryset = MarketItemReference.objects.all()

    def perform_update(self, serializer):
        serializer.save()
        recalculate_prices(triggered_by=_request_actor(self.request), trigger_source="WEBSITE")

    def delete(self, request, *args, **kwargs):
        item = self.get_object()
        item.enabled = False
        item.save(update_fields=["enabled", "updated_at"])
        recalculate_prices(triggered_by=_request_actor(request), trigger_source="WEBSITE")
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCityListView(generics.ListAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = CitySerializer
    queryset = City.objects.all()


class AdminCityModifierListView(generics.ListAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = CityMarketModifierSerializer

    def get_queryset(self):
        return _filter(CityMarketModifier.objects.all(), self.request, ("city_id", "category", "active"))


class AdminCityModifierDetailView(generics.UpdateAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = CityMarketModifierSerializer
    queryset = CityMarketModifier.objects.all()


class AdminCalculatedPriceListView(generics.ListAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = CalculatedMarketPriceSerializer

    def get_queryset(self):
        return _filter(CalculatedMarketPrice.objects.all(), self.request, ("city_id", "market_type", "item_id", "category"))


class AdminCounterListView(generics.ListAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = MerchantCounterSerializer

    def get_queryset(self):
        return _filter(MerchantCounter.objects.all(), self.request, ("city_id", "type", "owner_type", "owner_id", "active"))


class AdminCounterDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = MerchantCounterSerializer
    queryset = MerchantCounter.objects.all()


class AdminCounterModerationListView(APIView):
    permission_classes = [IsRenbloodAdmin]

    def get(self, request):
        counters = list(MerchantCounter.objects.all().order_by())
        counters = _apply_counter_moderation_filters(counters, request)
        items_by_counter = {}
        for item in MerchantCounterItem.objects.all().order_by():
            items_by_counter.setdefault(item.counter_id, []).append(item)
        transactions_by_counter = {}
        for transaction in MarketTransaction.objects.all().order_by():
            transactions_by_counter.setdefault(transaction.counter_id, []).append(transaction)
        enriched = [
            _attach_counter_metrics(
                counter,
                items_by_counter.get(counter.id, []),
                transactions_by_counter.get(counter.id, []),
            )
            for counter in counters
        ]
        return Response(AdminCounterModerationSerializer(enriched, many=True).data)


class AdminCounterDisableView(APIView):
    permission_classes = [IsRenbloodAdmin]

    def post(self, request, pk):
        counter = get_object_or_404(MerchantCounter, pk=pk)
        serializer = CounterModerationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        set_counter_moderation(
            counter,
            ModerationStatus.DISABLED,
            performed_by=_request_actor(request),
            reason=serializer.validated_data["reason"],
        )
        counter.itemCount = None
        counter.transactionCount = None
        counter.ownerGains = None
        return Response(AdminCounterModerationSerializer(counter).data)


class AdminCounterEnableView(APIView):
    permission_classes = [IsRenbloodAdmin]

    def post(self, request, pk):
        counter = get_object_or_404(MerchantCounter, pk=pk)
        set_counter_moderation(
            counter,
            ModerationStatus.ACTIVE,
            performed_by=_request_actor(request),
        )
        counter.itemCount = None
        counter.transactionCount = None
        counter.ownerGains = None
        return Response(AdminCounterModerationSerializer(counter).data)


class AdminCounterFlagView(APIView):
    permission_classes = [IsRenbloodAdmin]

    def post(self, request, pk):
        counter = get_object_or_404(MerchantCounter, pk=pk)
        serializer = CounterModerationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        set_counter_moderation(
            counter,
            ModerationStatus.FLAGGED,
            performed_by=_request_actor(request),
            reason=serializer.validated_data["reason"],
        )
        counter.itemCount = None
        counter.transactionCount = None
        counter.ownerGains = None
        return Response(AdminCounterModerationSerializer(counter).data)


class AdminCounterAuditView(APIView):
    permission_classes = [IsRenbloodAdmin]

    def get(self, request, pk):
        counter = get_object_or_404(MerchantCounter, pk=pk)
        items = list(MerchantCounterItem.objects.filter(counter=counter))
        transactions = list(MarketTransaction.objects.filter(counter=counter)[:50])
        withdrawals = list(MarketWithdrawal.objects.filter(counter_id=counter.counter_id)[:50])
        moderation_logs = list(counter.moderation_logs.all()[:50])
        counter = _attach_counter_metrics(counter, items, transactions)
        payload = {
            "counter": counter,
            "items": items,
            "transactions": transactions,
            "withdrawals": withdrawals,
            "moderationLogs": moderation_logs,
            "owner": {
                "ownerType": counter.owner_type,
                "ownerId": counter.owner_id,
                "ownerName": counter.owner_name,
            },
            "riskIndicators": getattr(counter, "riskIndicators", []),
        }
        return Response(AdminCounterAuditSerializer(payload).data)


class AdminTransactionListView(generics.ListAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = MarketTransactionSerializer

    def get_queryset(self):
        return _filter(MarketTransaction.objects.all(), self.request, ("counter_id", "city_id", "player_uuid", "owner_id", "action", "item_id"))


class AdminWithdrawalListView(generics.ListAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = MarketWithdrawalSerializer

    def get_queryset(self):
        return _filter(
            MarketWithdrawal.objects.all(),
            self.request,
            ("counter_id", "owner_uuid", "source"),
        )


class AdminCounterWithdrawalListView(generics.ListAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = MarketWithdrawalSerializer

    def get_queryset(self):
        counter = get_object_or_404(MerchantCounter, pk=self.kwargs["pk"])
        return MarketWithdrawal.objects.filter(counter_id=counter.counter_id)


class AdminCalculationRunListView(generics.ListAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = PriceCalculationRunSerializer
    queryset = PriceCalculationRun.objects.all()


class AdminEconomyConfigView(APIView):
    permission_classes = [IsRenbloodAdmin]

    def get(self, request):
        return Response(MarketEconomyConfigSerializer(get_economy_config()).data)

    def post(self, request):
        instance = MarketEconomyConfig.objects.first()
        serializer = MarketEconomyConfigSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        return Response(MarketEconomyConfigSerializer(config).data)


class AdminEconomyActivityView(APIView):
    permission_classes = [IsRenbloodAdmin]

    def get(self, request):
        window_days = request.query_params.get("activityWindowDays")
        window_days = int(window_days) if window_days else None
        buckets, config = summarize_activity(window_days=window_days)
        serialized = [
            {
                "cityId": bucket["city"].id if bucket["city"] else None,
                "cityName": bucket["city"].name if bucket["city"] else None,
                "itemId": bucket["item_id"],
                "category": bucket["category"],
                "buyQuantity": bucket["buy_quantity"],
                "sellQuantity": bucket["sell_quantity"],
                "buyTransactionCount": bucket["buy_transaction_count"],
                "sellTransactionCount": bucket["sell_transaction_count"],
                "periodStart": bucket["period_start"],
                "periodEnd": bucket["period_end"],
            }
            for bucket in buckets
        ]
        return Response({
            "dynamicEconomyEnabled": config.dynamic_economy_enabled,
            "activityWindowDays": window_days or config.activity_window_days,
            "rows": serialized,
        })


class AdminEconomyActivityModifierListView(generics.ListAPIView):
    permission_classes = [IsRenbloodAdmin]
    serializer_class = MarketActivityModifierSerializer

    def get_queryset(self):
        queryset = _filter(MarketActivityModifier.objects.all(), self.request, ("city_id", "item_id", "category", "calculation_version"))
        period_start = self.request.query_params.get("periodStart")
        period_end = self.request.query_params.get("periodEnd")
        if period_start:
            queryset = queryset.filter(period_start__gte=period_start)
        if period_end:
            queryset = queryset.filter(period_end__lte=period_end)
        return queryset


class AdminEconomyRecomputeActivityView(APIView):
    permission_classes = [IsRenbloodAdmin]

    def post(self, request):
        serializer = RecomputeActivitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = recompute_activity_modifiers(
            triggered_by=_request_actor(request),
            calculation_version=serializer.validated_data.get("calculationVersion"),
            window_days=serializer.validated_data.get("activityWindowDays"),
        )
        return Response({
            "periodStart": result["periodStart"],
            "periodEnd": result["periodEnd"],
            "windowDays": result["windowDays"],
            "dynamicEconomyEnabled": result["dynamicEconomyEnabled"],
            "modifiers": MarketActivityModifierSerializer(result["modifiers"], many=True).data,
        })


class MinecraftCurrentPricesView(APIView):
    permission_classes = [HasMinecraftApiKey]

    def get(self, request):
        active_cities = {city.id: city for city in City.objects.all().order_by() if city.active}
        enabled_items = {
            item.item_id: item for item in MarketItemReference.objects.all().order_by() if item.enabled
        }
        active_types = {config.type for config in MarketTypeConfig.objects.all().order_by() if config.active}
        successful_runs = [
            run for run in PriceCalculationRun.objects.all().order_by() if run.status == "SUCCESS"
        ]
        latest_run = max(
            successful_runs,
            key=lambda run: run.finished_at or run.started_at,
            default=None,
        )
        all_prices = list(CalculatedMarketPrice.objects.all().order_by())
        if latest_run:
            version = latest_run.calculation_version
            calculated_at = latest_run.finished_at or latest_run.started_at
        else:
            latest_price = max(all_prices, key=lambda price: price.calculated_at, default=None)
            version = latest_price.calculation_version if latest_price else None
            calculated_at = latest_price.calculated_at if latest_price else None
        prices = [
            price for price in all_prices
            if version
            and price.calculation_version == version
            and price.city_id in active_cities
            and price.item_id in enabled_items
            and price.market_type in active_types
        ]
        if prices:
            calculated_at = max(price.calculated_at for price in prices)
        logger.info("Minecraft market prices served version=%s prices=%s", version, len(prices))
        return Response({
            "calculationVersion": version,
            "calculatedAt": calculated_at,
            "prices": [{
                "cityId": price.city_id,
                "cityName": active_cities[price.city_id].name,
                "marketType": price.market_type,
                "itemId": price.item_id,
                "displayName": enabled_items[price.item_id].display_name,
                "category": price.category,
                "calculatedPrice": max(1, price.calculated_price),
                "buyPrice": max(1, price.buy_price),
                "sellPrice": max(1, price.sell_price),
            } for price in prices],
        })


class MinecraftCounterListCreateView(generics.ListCreateAPIView):
    permission_classes = [HasMinecraftApiKey]
    serializer_class = MinecraftCounterSerializer

    def get_queryset(self):
        return _filter(MerchantCounter.objects.all(), self.request, ("city_id", "type", "owner_type", "owner_id", "active"))

    def create(self, request, *args, **kwargs):
        counter_id = request.data.get("counterId")
        if not counter_id:
            return Response(
                {"counterId": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing = MerchantCounter.objects.filter(counter_id=counter_id).first() if counter_id else None
        serializer = self.get_serializer(existing, data=request.data, partial=bool(existing))
        serializer.is_valid(raise_exception=True)
        counter = serializer.save()
        logger.info(
            "Minecraft counter %s counter_id=%s",
            "updated" if existing else "created",
            counter.counter_id,
        )
        return Response(
            self.get_serializer(counter).data,
            status=status.HTTP_200_OK if existing else status.HTTP_201_CREATED,
        )


class MinecraftCounterDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [HasMinecraftApiKey]
    serializer_class = MinecraftCounterSerializer
    queryset = MerchantCounter.objects.all()
    lookup_field = "counter_id"
    lookup_url_kwarg = "counter_id"

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        logger.info("Minecraft counter updated counter_id=%s", kwargs["counter_id"])
        return response


class MinecraftReferenceItemListView(generics.ListAPIView):
    permission_classes = [HasMinecraftApiKey]
    serializer_class = MinecraftReferenceItemSerializer

    def get_queryset(self):
        return sorted(
            (item for item in MarketItemReference.objects.all().order_by() if item.enabled),
            key=lambda item: item.item_id,
        )


class MinecraftXpReferenceItemListView(generics.ListAPIView):
    permission_classes = [HasMinecraftApiKey]
    serializer_class = MinecraftXpReferenceSerializer

    def get_queryset(self):
        return sorted(
            (
                item for item in MarketItemReference.objects.all().order_by()
                if item.enabled and item.reference_xp is not None
            ),
            key=lambda item: item.item_id,
        )


class MinecraftCounterItemListCreateView(APIView):
    permission_classes = [HasMinecraftApiKey]

    def get_counter(self, counter_id):
        return get_object_or_404(MerchantCounter, counter_id=counter_id)

    def get(self, request, counter_id):
        counter = self.get_counter(counter_id)
        items = MerchantCounterItem.objects.filter(counter=counter)
        return Response(MinecraftCounterItemSerializer(items, many=True).data)

    def post(self, request, counter_id):
        counter = self.get_counter(counter_id)
        item_id = request.data.get("itemId")
        existing = MerchantCounterItem.objects.filter(counter=counter, item_id=item_id).first() if item_id else None
        if existing and existing.active:
            return Response(
                {"itemId": ["Cet item existe déjà dans ce comptoir."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MinecraftCounterItemSerializer(
            existing, data=request.data, context={"counter": counter}, partial=bool(existing),
        )
        serializer.is_valid(raise_exception=True)
        item = serializer.save(counter=counter, active=request.data.get("active", True))
        logger.info(
            "Minecraft counter item %s counter_id=%s item_id=%s",
            "reactivated" if existing else "created", counter.counter_id, item.item_id,
        )
        return Response(
            MinecraftCounterItemSerializer(item).data,
            status=status.HTTP_200_OK if existing else status.HTTP_201_CREATED,
        )


class MinecraftCounterItemDetailView(APIView):
    permission_classes = [HasMinecraftApiKey]

    def get_objects(self, counter_id, item_id):
        counter = get_object_or_404(MerchantCounter, counter_id=counter_id)
        item = get_object_or_404(MerchantCounterItem, counter=counter, item_id=item_id)
        return counter, item

    def put(self, request, counter_id, item_id):
        counter, item = self.get_objects(counter_id, item_id)
        serializer = MinecraftCounterItemSerializer(
            item, data=request.data, partial=True, context={"counter": counter},
        )
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        logger.info("Minecraft counter item updated counter_id=%s item_id=%s", counter.counter_id, item.item_id)
        return Response(MinecraftCounterItemSerializer(item).data)

    def delete(self, request, counter_id, item_id):
        counter, item = self.get_objects(counter_id, item_id)
        item.active = False
        item.save(update_fields=["active", "updated_at"])
        logger.info("Minecraft counter item disabled counter_id=%s item_id=%s", counter.counter_id, item.item_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MinecraftTransactionCreateView(generics.CreateAPIView):
    permission_classes = [HasMinecraftApiKey]
    serializer_class = MinecraftTransactionSerializer

    def perform_create(self, serializer):
        transaction = serializer.save()
        logger.info(
            "Minecraft market transaction recorded counter_id=%s action=%s item_id=%s quantity=%s total=%s",
            transaction.counter.counter_id, transaction.action, transaction.item_id,
            transaction.quantity, transaction.total_price,
        )


class MinecraftWithdrawalCreateView(generics.CreateAPIView):
    permission_classes = [HasMinecraftApiKey]
    serializer_class = MinecraftWithdrawalSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["counter_id"] = self.kwargs["counter_id"]
        return context

    def perform_create(self, serializer):
        counter_id = self.kwargs["counter_id"]
        counter = MerchantCounter.objects.filter(counter_id=counter_id).first()
        owner_uuid = serializer.validated_data["owner_uuid"]
        if counter and counter.owner_id and counter.owner_id != owner_uuid:
            logger.warning(
                "Minecraft market withdrawal owner mismatch counter_id=%s expected_owner_id=%s actual_owner_uuid=%s",
                counter.counter_id,
                counter.owner_id,
                owner_uuid,
            )
        withdrawal = serializer.save(
            counter_id=counter_id,
            source="MINECRAFT",
        )
        if counter:
            counter.last_owner_interaction_at = withdrawal.withdrawn_at
            refresh_counter_risk(counter, save=False)
            counter.save(update_fields=["last_owner_interaction_at", "risk_score", "updated_at"])
        logger.info(
            "Minecraft market withdrawal recorded counter_id=%s owner_uuid=%s amount=%s linked_counter=%s",
            withdrawal.counter_id,
            withdrawal.owner_uuid,
            withdrawal.amount,
            bool(counter),
        )


class MinecraftOwnedCounterListView(generics.ListAPIView):
    permission_classes = [HasMinecraftApiKey]
    serializer_class = MinecraftCounterSerializer

    def get_queryset(self):
        return MerchantCounter.objects.filter(owner_type="PLAYER", owner_id=self.kwargs["player_uuid"], active=True)


class MinecraftCounterTransactionListView(generics.ListAPIView):
    permission_classes = [HasMinecraftApiKey]
    serializer_class = MinecraftTransactionSerializer

    def get_queryset(self):
        counter = get_object_or_404(MerchantCounter, counter_id=self.kwargs["counter_id"])
        return MarketTransaction.objects.filter(counter=counter)


class PublicMarketPricesView(APIView):
    permission_classes = []

    def get(self, request):
        public_ids = getattr(settings, "PUBLIC_MARKET_ITEM_IDS", [
            "minecraft:bread", "minecraft:iron_ingot", "minecraft:oak_log",
        ])
        active_cities = {
            city.id: city
            for city in City.objects.all().order_by()
            if city.active
        }
        successful_runs = [
            run for run in PriceCalculationRun.objects.all().order_by()
            if run.status == "SUCCESS"
        ]
        latest_run = max(
            successful_runs,
            key=lambda run: run.finished_at or run.started_at,
            default=None,
        )
        prices = [
            price
            for price in CalculatedMarketPrice.objects.all().order_by()
            if latest_run
            and price.calculation_version == latest_run.calculation_version
            and price.item_id in public_ids
            and price.city_id in active_cities
        ]
        by_city = {}
        for price in prices:
            city_model = active_cities[price.city_id]
            city = by_city.setdefault(price.city_id, {"cityId": price.city_id, "cityName": city_model.name, "prices": []})
            city["prices"].append({
                "itemId": price.item_id,
                "buyPrice": price.buy_price,
                "marketType": price.market_type,
            })
        return Response({
            "calculationVersion": latest_run.calculation_version if latest_run else None,
            "calculatedAt": latest_run.finished_at if latest_run else None,
            "cities": list(by_city.values()),
        })
