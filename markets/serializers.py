from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    CalculatedMarketPrice, City, CityMarketModifier, MarketItemReference,
    MarketActivityModifier, MarketEconomyConfig, MarketModerationLog, MarketTransaction,
    MarketType, MarketWithdrawal, MerchantCounter, MerchantCounterItem,
    ModerationStatus, PriceCalculationRun, StockMode,
)
from .services import record_transaction


class ValidatingModelSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance or self.Meta.model()
        model_fields = {field.name for field in instance._meta.fields}
        for key, value in attrs.items():
            if key in model_fields:
                setattr(instance, key, value)
        exclude = [field.name for field in instance._meta.fields if field.name not in attrs] if not self.instance else None
        try:
            instance.full_clean(exclude=exclude, validate_unique=False)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return attrs


class MarketItemReferenceSerializer(ValidatingModelSerializer):
    class Meta:
        model = MarketItemReference
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = "__all__"


class CityMarketModifierSerializer(ValidatingModelSerializer):
    class Meta:
        model = CityMarketModifier
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class MerchantCounterItemSerializer(ValidatingModelSerializer):
    class Meta:
        model = MerchantCounterItem
        fields = "__all__"
        read_only_fields = ("id", "counter", "created_at", "updated_at")


class MerchantCounterSerializer(ValidatingModelSerializer):
    items = MerchantCounterItemSerializer(many=True, required=False)

    class Meta:
        model = MerchantCounter
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        counter_type = attrs.get("type", getattr(self.instance, "type", None))
        items = attrs.get("items", [])
        item_ids = [item["item_id"] for item in items]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError({"items": "An item_id can only appear once in a counter."})
        if counter_type == "PLAYER_MARKET":
            invalid = [item["item_id"] for item in items if item.get("stock_mode", "UNLIMITED") != "PLAYER_INVENTORY"]
            if invalid:
                raise serializers.ValidationError({"items": "Player market items must use PLAYER_INVENTORY."})
        return attrs

    def create(self, validated_data):
        items = validated_data.pop("items", [])
        if validated_data.get("moderation_status") == ModerationStatus.DISABLED:
            validated_data["active"] = False
        counter = super().create(validated_data)
        for item in items:
            MerchantCounterItem.objects.create(counter=counter, **item)
        return counter

    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        if validated_data.get("moderation_status") == ModerationStatus.DISABLED:
            validated_data["active"] = False
        counter = super().update(instance, validated_data)
        if items is not None:
            for item in items:
                MerchantCounterItem.objects.update_or_create(
                    counter=counter,
                    item_id=item["item_id"],
                    defaults=item,
                )
        return counter


class CalculatedMarketPriceSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = CalculatedMarketPrice
        fields = "__all__"


class MarketTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketTransaction
        fields = "__all__"
        read_only_fields = ("id", "city", "owner_type", "owner_id", "item_display_name", "unit_price", "total_price", "owner_gain", "created_at")

    def create(self, validated_data):
        return record_transaction(validated_data)


class MarketWithdrawalSerializer(serializers.ModelSerializer):
    counterId = serializers.CharField(source="counter_id")
    ownerUuid = serializers.CharField(source="owner_uuid")
    ownerName = serializers.CharField(source="owner_name")
    withdrawnAt = serializers.DateTimeField(source="withdrawn_at")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = MarketWithdrawal
        fields = (
            "id", "counterId", "ownerUuid", "ownerName",
            "amount", "withdrawnAt", "source", "createdAt",
        )
        read_only_fields = ("id", "createdAt")


class MarketModerationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketModerationLog
        fields = "__all__"


class MarketEconomyConfigSerializer(ValidatingModelSerializer):
    dynamicEconomyEnabled = serializers.BooleanField(source="dynamic_economy_enabled", required=False)
    activityWindowDays = serializers.IntegerField(source="activity_window_days", required=False, min_value=1)
    maxActivityModifierUp = serializers.DecimalField(source="max_activity_modifier_up", required=False, max_digits=8, decimal_places=4)
    maxActivityModifierDown = serializers.DecimalField(source="max_activity_modifier_down", required=False, max_digits=8, decimal_places=4)
    minTransactionsForImpact = serializers.IntegerField(source="min_transactions_for_impact", required=False, min_value=0)
    buyPressureWeight = serializers.DecimalField(source="buy_pressure_weight", required=False, max_digits=8, decimal_places=4)
    sellPressureWeight = serializers.DecimalField(source="sell_pressure_weight", required=False, max_digits=8, decimal_places=4)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = MarketEconomyConfig
        fields = (
            "id", "dynamicEconomyEnabled", "activityWindowDays", "maxActivityModifierUp",
            "maxActivityModifierDown", "minTransactionsForImpact", "buyPressureWeight",
            "sellPressureWeight", "updatedAt",
        )
        read_only_fields = ("id", "updatedAt")


class MarketActivityModifierSerializer(serializers.ModelSerializer):
    cityId = serializers.CharField(source="city_id", read_only=True, allow_null=True)
    cityName = serializers.CharField(source="city.name", read_only=True, allow_null=True)
    itemId = serializers.CharField(source="item_id")
    buyQuantity = serializers.IntegerField(source="buy_quantity")
    sellQuantity = serializers.IntegerField(source="sell_quantity")
    buyTransactionCount = serializers.IntegerField(source="buy_transaction_count")
    sellTransactionCount = serializers.IntegerField(source="sell_transaction_count")
    periodStart = serializers.DateTimeField(source="period_start")
    periodEnd = serializers.DateTimeField(source="period_end")
    activityModifier = serializers.DecimalField(source="activity_modifier", max_digits=8, decimal_places=4)
    calculationVersion = serializers.CharField(source="calculation_version", allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = MarketActivityModifier
        fields = (
            "id", "cityId", "cityName", "itemId", "category", "buyQuantity",
            "sellQuantity", "buyTransactionCount", "sellTransactionCount", "periodStart",
            "periodEnd", "activityModifier", "calculationVersion", "createdAt",
        )


class PriceCalculationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceCalculationRun
        fields = "__all__"


class MinecraftCounterItemSerializer(serializers.ModelSerializer):
    counterId = serializers.CharField(source="counter.counter_id", read_only=True)
    itemId = serializers.CharField(source="item_id")
    displayName = serializers.CharField(source="display_name")
    buyEnabled = serializers.BooleanField(source="buy_enabled", default=True)
    sellEnabled = serializers.BooleanField(source="sell_enabled", default=False)
    autoPrice = serializers.BooleanField(source="auto_price", default=True)
    manualBuyPrice = serializers.IntegerField(source="manual_buy_price", allow_null=True, required=False, min_value=1)
    manualSellPrice = serializers.IntegerField(source="manual_sell_price", allow_null=True, required=False, min_value=1)
    stockMode = serializers.ChoiceField(
        source="stock_mode", choices=(StockMode.UNLIMITED, StockMode.LIMITED),
        default=StockMode.UNLIMITED,
    )
    stockQuantity = serializers.IntegerField(source="stock_quantity", allow_null=True, required=False, min_value=0)
    localModifier = serializers.FloatField(source="local_modifier", default=1.0, min_value=0)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = MerchantCounterItem
        fields = (
            "id", "counterId", "itemId", "displayName", "buyEnabled", "sellEnabled",
            "autoPrice", "manualBuyPrice", "manualSellPrice", "stockMode",
            "stockQuantity", "localModifier", "active", "createdAt", "updatedAt",
        )
        read_only_fields = ("id", "counterId", "createdAt", "updatedAt")

    def validate(self, attrs):
        counter = self.context.get("counter")
        if counter and counter.type == MarketType.PLAYER_MARKET:
            raise serializers.ValidationError("PLAYER_MARKET is not supported yet.")

        item_id = attrs.get("item_id", getattr(self.instance, "item_id", None))
        auto_price = attrs.get("auto_price", getattr(self.instance, "auto_price", True))
        sell_enabled = attrs.get("sell_enabled", getattr(self.instance, "sell_enabled", False))
        manual_buy_price = attrs.get("manual_buy_price", getattr(self.instance, "manual_buy_price", None))
        manual_sell_price = attrs.get("manual_sell_price", getattr(self.instance, "manual_sell_price", None))
        stock_mode = attrs.get("stock_mode", getattr(self.instance, "stock_mode", StockMode.UNLIMITED))
        stock_quantity = attrs.get("stock_quantity", getattr(self.instance, "stock_quantity", None))

        reference = MarketItemReference.objects.filter(item_id=item_id).first()
        errors = {}
        if auto_price and not reference:
            errors["itemId"] = "itemId doit correspondre à un item de référence existant lorsque autoPrice est true."
        if not auto_price and manual_buy_price is None:
            errors["manualBuyPrice"] = "manualBuyPrice est requis lorsque autoPrice est false."
        if not auto_price and sell_enabled and manual_sell_price is None:
            errors["manualSellPrice"] = "manualSellPrice est requis lorsque sellEnabled est true et autoPrice est false."
        if stock_mode == StockMode.LIMITED and stock_quantity is None:
            errors["stockQuantity"] = "stockQuantity est requis lorsque stockMode vaut LIMITED."
        if errors:
            raise serializers.ValidationError(errors)
        if stock_mode == StockMode.UNLIMITED:
            attrs["stock_quantity"] = None
        if reference:
            attrs["category"] = reference.category
        if self.instance:
            attrs.pop("item_id", None)
        return attrs


class MinecraftReferenceItemSerializer(serializers.ModelSerializer):
    itemId = serializers.CharField(source="item_id", read_only=True)
    displayName = serializers.CharField(source="display_name", read_only=True)
    referencePrice = serializers.IntegerField(source="reference_price", read_only=True)

    class Meta:
        model = MarketItemReference
        fields = ("id", "itemId", "displayName", "category", "referencePrice", "enabled")
        read_only_fields = fields


class MinecraftCounterSerializer(ValidatingModelSerializer):
    counterId = serializers.CharField(source="counter_id", required=False)
    cityId = serializers.PrimaryKeyRelatedField(
        source="city", queryset=City.objects.all(), allow_null=True, required=False,
    )
    cityName = serializers.CharField(source="city.name", read_only=True, allow_null=True)
    ownerType = serializers.CharField(source="owner_type")
    ownerId = serializers.CharField(source="owner_id", allow_null=True, allow_blank=True, required=False)
    ownerName = serializers.CharField(source="owner_name", allow_null=True, allow_blank=True, required=False)
    moderationStatus = serializers.CharField(source="moderation_status", required=False)
    moderationReason = serializers.CharField(source="moderation_reason", allow_null=True, allow_blank=True, required=False)
    flaggedReason = serializers.CharField(source="flagged_reason", allow_null=True, allow_blank=True, required=False)
    createdSource = serializers.CharField(source="created_source", required=False)
    lastTransactionAt = serializers.DateTimeField(source="last_transaction_at", read_only=True)
    lastOwnerInteractionAt = serializers.DateTimeField(source="last_owner_interaction_at", read_only=True)
    riskScore = serializers.FloatField(source="risk_score", required=False, allow_null=True)
    buyModeEnabled = serializers.BooleanField(source="buy_mode_enabled", required=False, default=True)
    sellModeEnabled = serializers.BooleanField(source="sell_mode_enabled", required=False, default=False)
    items = MinecraftCounterItemSerializer(many=True, read_only=True)

    class Meta:
        model = MerchantCounter
        fields = (
            "id", "counterId", "name", "type", "cityId", "cityName", "ownerType",
            "ownerId", "ownerName", "world", "x", "y", "z", "active",
            "moderationStatus", "moderationReason", "flaggedReason", "createdSource",
            "riskScore", "lastTransactionAt", "lastOwnerInteractionAt",
            "buyModeEnabled", "sellModeEnabled", "items",
        )
        read_only_fields = ("id", "cityName", "items", "lastTransactionAt", "lastOwnerInteractionAt")

    def validate(self, attrs):
        if self.instance:
            attrs.pop("counter_id", None)
        return super().validate(attrs)

    def create(self, validated_data):
        validated_data.setdefault("created_by", validated_data.get("owner_id") or "minecraft-server")
        validated_data.setdefault("created_source", "MINECRAFT")
        return super().create(validated_data)


class MinecraftTransactionSerializer(serializers.ModelSerializer):
    counterId = serializers.SlugRelatedField(
        source="counter", slug_field="counter_id", queryset=MerchantCounter.objects.all(),
    )
    playerUuid = serializers.CharField(source="player_uuid")
    playerName = serializers.CharField(source="player_name")
    itemId = serializers.CharField(source="item_id")
    itemDisplayName = serializers.CharField(source="item_display_name", required=False)
    unitPrice = serializers.IntegerField(source="unit_price", min_value=1)
    totalPrice = serializers.IntegerField(source="total_price", min_value=1)
    ownerGain = serializers.IntegerField(source="owner_gain", min_value=0, required=False)
    ownerType = serializers.CharField(source="owner_type", read_only=True)
    ownerId = serializers.CharField(source="owner_id", read_only=True, allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = MarketTransaction
        fields = (
            "id", "counterId", "playerUuid", "playerName", "itemId",
            "itemDisplayName", "action", "quantity", "unitPrice", "totalPrice",
            "ownerGain", "ownerType", "ownerId", "createdAt",
        )
        read_only_fields = ("id", "ownerType", "ownerId", "createdAt")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        expected_total = attrs["quantity"] * attrs["unit_price"]
        if attrs["total_price"] != expected_total:
            raise serializers.ValidationError({
                "totalPrice": "totalPrice must equal quantity multiplied by unitPrice.",
            })
        expected_gain = expected_total if attrs["action"] == "BUY" else 0
        supplied_gain = attrs.get("owner_gain", expected_gain)
        if supplied_gain != expected_gain:
            raise serializers.ValidationError({
                "ownerGain": f"ownerGain must be {expected_gain} for this transaction.",
            })
        attrs["owner_gain"] = expected_gain
        return attrs

    def create(self, validated_data):
        return record_transaction(validated_data)


class MinecraftWithdrawalSerializer(serializers.ModelSerializer):
    counterId = serializers.CharField(source="counter_id")
    ownerUuid = serializers.CharField(source="owner_uuid")
    ownerName = serializers.CharField(source="owner_name")
    withdrawnAt = serializers.DateTimeField(source="withdrawn_at")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = MarketWithdrawal
        fields = (
            "id", "counterId", "ownerUuid", "ownerName", "amount",
            "withdrawnAt", "source", "createdAt",
        )
        read_only_fields = ("id", "source", "createdAt")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        path_counter_id = self.context.get("counter_id")
        supplied_counter_id = attrs.get("counter_id")
        if request and supplied_counter_id and path_counter_id and supplied_counter_id != path_counter_id:
            raise serializers.ValidationError({
                "counterId": "counterId must match the counter id in the URL.",
            })
        return attrs


class AdminCounterModerationSerializer(serializers.ModelSerializer):
    counterId = serializers.CharField(source="counter_id", read_only=True)
    cityId = serializers.CharField(source="city_id", read_only=True, allow_null=True)
    cityName = serializers.CharField(source="city.name", read_only=True, allow_null=True)
    ownerType = serializers.CharField(source="owner_type", read_only=True)
    ownerId = serializers.CharField(source="owner_id", read_only=True, allow_null=True)
    ownerName = serializers.CharField(source="owner_name", read_only=True, allow_null=True)
    moderationStatus = serializers.CharField(source="moderation_status", read_only=True)
    moderationReason = serializers.CharField(source="moderation_reason", read_only=True, allow_null=True)
    disabledBy = serializers.CharField(source="disabled_by", read_only=True, allow_null=True)
    disabledAt = serializers.DateTimeField(source="disabled_at", read_only=True)
    flaggedReason = serializers.CharField(source="flagged_reason", read_only=True, allow_null=True)
    lastTransactionAt = serializers.DateTimeField(source="last_transaction_at", read_only=True)
    lastOwnerInteractionAt = serializers.DateTimeField(source="last_owner_interaction_at", read_only=True)
    createdSource = serializers.CharField(source="created_source", read_only=True)
    riskScore = serializers.FloatField(source="risk_score", read_only=True, allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    itemCount = serializers.IntegerField(read_only=True, allow_null=True)
    transactionCount = serializers.IntegerField(read_only=True, allow_null=True)
    ownerGains = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = MerchantCounter
        fields = (
            "id", "counterId", "name", "type", "cityId", "cityName", "ownerType",
            "ownerId", "ownerName", "world", "x", "y", "z", "active",
            "moderationStatus", "moderationReason", "disabledBy", "disabledAt",
            "flaggedReason", "lastTransactionAt", "lastOwnerInteractionAt", "createdSource",
            "riskScore", "itemCount", "transactionCount", "ownerGains", "createdAt", "updatedAt",
        )


class CounterModerationActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False)


class AdminCounterAuditSerializer(serializers.Serializer):
    counter = AdminCounterModerationSerializer()
    items = MerchantCounterItemSerializer(many=True)
    transactions = MarketTransactionSerializer(many=True)
    withdrawals = MarketWithdrawalSerializer(many=True)
    moderationLogs = MarketModerationLogSerializer(many=True)
    owner = serializers.DictField()
    riskIndicators = serializers.ListField(child=serializers.DictField())


class RecomputeActivitySerializer(serializers.Serializer):
    activityWindowDays = serializers.IntegerField(required=False, min_value=1)
    calculationVersion = serializers.CharField(required=False, allow_blank=False)
