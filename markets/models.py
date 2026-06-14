import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from djongo import models


def new_id():
    return str(uuid.uuid4())


class EconomicCategory(models.TextChoices):
    FOOD = "FOOD", "Food"
    WOOD = "WOOD", "Wood"
    STONE = "STONE", "Stone"
    IRON = "IRON", "Iron"
    TOOLS = "TOOLS", "Tools"
    WEAPONS = "WEAPONS", "Weapons"
    ARMOR = "ARMOR", "Armor"
    FARMING = "FARMING", "Farming"
    ALCHEMY = "ALCHEMY", "Alchemy"
    LUXURY = "LUXURY", "Luxury"
    CONSTRUCTION = "CONSTRUCTION", "Construction"
    RARE = "RARE", "Rare"
    GUILD = "GUILD", "Guild"
    OTHER = "OTHER", "Other"


class MarketType(models.TextChoices):
    SHOP = "SHOP", "Shop"
    CITY_MARKET = "CITY_MARKET", "City market"
    TEMPORARY_MARKET = "TEMPORARY_MARKET", "Temporary market"
    GUILD_COUNTER = "GUILD_COUNTER", "Guild counter"
    PLAYER_MARKET = "PLAYER_MARKET", "Player market"


class ModerationStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    DISABLED = "DISABLED", "Disabled"
    PENDING_REVIEW = "PENDING_REVIEW", "Pending review"
    FLAGGED = "FLAGGED", "Flagged"


class OwnerType(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    PLAYER = "PLAYER", "Player"
    CITY = "CITY", "City"
    GUILD = "GUILD", "Guild"


class StockMode(models.TextChoices):
    UNLIMITED = "UNLIMITED", "Unlimited"
    LIMITED = "LIMITED", "Limited"
    PLAYER_INVENTORY = "PLAYER_INVENTORY", "Player inventory"


class CounterCreatedSource(models.TextChoices):
    MINECRAFT = "MINECRAFT", "Minecraft"
    WEBSITE = "WEBSITE", "Website"
    SYSTEM = "SYSTEM", "System"


class UuidModel(models.Model):
    id = models.CharField(primary_key=True, max_length=36, default=new_id, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(UuidModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class MarketItemReference(TimestampedModel):
    item_id = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=EconomicCategory.choices)
    reference_price = models.BigIntegerField(validators=[MinValueValidator(1)])
    reference_xp = models.FloatField(null=True, blank=True)
    min_price = models.BigIntegerField(default=1, validators=[MinValueValidator(1)])
    max_price = models.BigIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "market_item_references"
        ordering = ["item_id"]

    def clean(self):
        if self.max_price is not None and self.max_price < self.min_price:
            raise ValidationError({"max_price": "max_price must be greater than or equal to min_price."})


class City(TimestampedModel):
    name = models.CharField(max_length=255, unique=True)
    active = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "market_cities"
        ordering = ["name"]


class MarketCategory(UuidModel):
    code = models.CharField(max_length=32, choices=EconomicCategory.choices, unique=True)
    display_name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "market_categories"
        ordering = ["code"]


class CityMarketModifier(TimestampedModel):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="market_modifiers")
    category = models.CharField(max_length=32, choices=EconomicCategory.choices)
    modifier = models.DecimalField(max_digits=8, decimal_places=4, default=1, validators=[MinValueValidator(Decimal("0"))])
    reason = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "city_market_modifiers"
        unique_together = ("city", "category")


class MarketTypeConfig(UuidModel):
    type = models.CharField(max_length=32, choices=MarketType.choices, unique=True)
    display_name = models.CharField(max_length=255)
    base_modifier = models.DecimalField(max_digits=8, decimal_places=4, default=1, validators=[MinValueValidator(Decimal("0"))])
    tax_rate = models.DecimalField(
        max_digits=8, decimal_places=4, default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    active = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "market_type_configs"


class MerchantCounter(TimestampedModel):
    counter_id = models.CharField(max_length=255, unique=True, default=new_id)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=32, choices=MarketType.choices)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name="counters")
    owner_type = models.CharField(max_length=16, choices=OwnerType.choices)
    owner_id = models.CharField(max_length=255, null=True, blank=True)
    owner_name = models.CharField(max_length=255, null=True, blank=True)
    world = models.CharField(max_length=255)
    x = models.IntegerField()
    y = models.IntegerField()
    z = models.IntegerField()
    active = models.BooleanField(default=True)
    moderation_status = models.CharField(max_length=32, choices=ModerationStatus.choices, default=ModerationStatus.ACTIVE)
    moderation_reason = models.TextField(null=True, blank=True)
    disabled_by = models.CharField(max_length=255, null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    flagged_reason = models.TextField(null=True, blank=True)
    last_transaction_at = models.DateTimeField(null=True, blank=True)
    last_owner_interaction_at = models.DateTimeField(null=True, blank=True)
    created_source = models.CharField(max_length=32, choices=CounterCreatedSource.choices, default=CounterCreatedSource.MINECRAFT)
    risk_score = models.FloatField(null=True, blank=True)
    sell_mode_enabled = models.BooleanField(default=False)
    buy_mode_enabled = models.BooleanField(default=True)
    created_by = models.CharField(max_length=255)

    class Meta:
        db_table = "merchant_counters"
        unique_together = ("world", "x", "y", "z")
        ordering = ["name"]

    def clean(self):
        if self.owner_type == OwnerType.PLAYER and not self.owner_id:
            raise ValidationError({"owner_id": "A player-owned counter requires owner_id."})
        if self.moderation_status == ModerationStatus.DISABLED and self.active:
            raise ValidationError({"active": "Disabled counters cannot remain active."})
        if not self.active and self.moderation_status == ModerationStatus.ACTIVE:
            raise ValidationError({"moderation_status": "Inactive counters cannot have ACTIVE moderation status."})


class MerchantCounterItem(TimestampedModel):
    counter = models.ForeignKey(MerchantCounter, on_delete=models.CASCADE, related_name="items")
    item_id = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=EconomicCategory.choices, default=EconomicCategory.OTHER)
    buy_enabled = models.BooleanField(default=True)
    sell_enabled = models.BooleanField(default=False)
    auto_price = models.BooleanField(default=True)
    manual_buy_price = models.BigIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    manual_sell_price = models.BigIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    stock_mode = models.CharField(max_length=32, choices=StockMode.choices, default=StockMode.UNLIMITED)
    stock_quantity = models.BigIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    local_modifier = models.DecimalField(max_digits=8, decimal_places=4, default=1, validators=[MinValueValidator(Decimal("0"))])
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "merchant_counter_items"
        unique_together = ("counter", "item_id")
        ordering = ["display_name"]

    def clean(self):
        if not self.auto_price and self.buy_enabled and self.manual_buy_price is None:
            raise ValidationError({"manual_buy_price": "Manual buy price is required when auto_price is disabled."})
        if not self.auto_price and self.sell_enabled and self.manual_sell_price is None:
            raise ValidationError({"manual_sell_price": "Manual sell price is required when auto_price is disabled."})
        if self.stock_mode == StockMode.LIMITED and self.stock_quantity is None:
            raise ValidationError({"stock_quantity": "Limited stock requires stock_quantity."})
        if self.counter_id and self.counter.type == MarketType.PLAYER_MARKET and self.stock_mode != StockMode.PLAYER_INVENTORY:
            raise ValidationError({"stock_mode": "Player markets must use PLAYER_INVENTORY."})


class CalculatedMarketPrice(UuidModel):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="calculated_prices")
    market_type = models.CharField(max_length=32, choices=MarketType.choices)
    item_id = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=EconomicCategory.choices)
    calculated_price = models.BigIntegerField(validators=[MinValueValidator(1)])
    buy_price = models.BigIntegerField(validators=[MinValueValidator(1)])
    sell_price = models.BigIntegerField(validators=[MinValueValidator(1)])
    calculation_version = models.CharField(max_length=64)
    calculated_at = models.DateTimeField()

    class Meta:
        db_table = "calculated_market_prices"
        unique_together = ("city", "market_type", "item_id")


class MarketTransaction(UuidModel):
    ACTION_CHOICES = (("BUY", "Buy"), ("SELL", "Sell"))

    counter = models.ForeignKey(MerchantCounter, on_delete=models.PROTECT, related_name="transactions")
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name="market_transactions")
    player_uuid = models.CharField(max_length=255)
    player_name = models.CharField(max_length=255)
    owner_type = models.CharField(max_length=16, choices=OwnerType.choices)
    owner_id = models.CharField(max_length=255, null=True, blank=True)
    item_id = models.CharField(max_length=255)
    item_display_name = models.CharField(max_length=255)
    action = models.CharField(max_length=8, choices=ACTION_CHOICES)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.BigIntegerField(validators=[MinValueValidator(1)])
    total_price = models.BigIntegerField(validators=[MinValueValidator(1)])
    owner_gain = models.BigIntegerField(default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "market_transactions"
        ordering = ["-created_at"]


class MarketWithdrawal(UuidModel):
    SOURCE_CHOICES = (("MINECRAFT", "Minecraft"),)

    counter_id = models.CharField(max_length=255)
    owner_uuid = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    amount = models.BigIntegerField(validators=[MinValueValidator(1)])
    withdrawn_at = models.DateTimeField()
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default="MINECRAFT")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "market_withdrawals"
        ordering = ["-withdrawn_at", "-created_at"]


class MarketModerationLog(TimestampedModel):
    ACTION_CHOICES = (
        ("DISABLED", "Disabled"),
        ("ENABLED", "Enabled"),
        ("FLAGGED", "Flagged"),
        ("STATUS_SYNC", "Status sync"),
    )

    counter = models.ForeignKey(MerchantCounter, on_delete=models.CASCADE, related_name="moderation_logs")
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    reason = models.TextField(null=True, blank=True)
    performed_by = models.CharField(max_length=255, null=True, blank=True)
    previous_status = models.CharField(max_length=32, choices=ModerationStatus.choices, null=True, blank=True)
    new_status = models.CharField(max_length=32, choices=ModerationStatus.choices)

    class Meta:
        db_table = "market_moderation_logs"
        ordering = ["-created_at"]


class MarketEconomyConfig(UuidModel):
    dynamic_economy_enabled = models.BooleanField(default=False)
    activity_window_days = models.PositiveIntegerField(default=7, validators=[MinValueValidator(1)])
    max_activity_modifier_up = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal("1.1500"),
        validators=[MinValueValidator(Decimal("1.0000"))],
    )
    max_activity_modifier_down = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal("0.8500"),
        validators=[MinValueValidator(Decimal("0.0100")), MaxValueValidator(Decimal("1.0000"))],
    )
    min_transactions_for_impact = models.PositiveIntegerField(default=10)
    buy_pressure_weight = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal("0.0100"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    sell_pressure_weight = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal("0.0100"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "market_economy_config"

    def clean(self):
        if self.max_activity_modifier_down > self.max_activity_modifier_up:
            raise ValidationError({
                "max_activity_modifier_down": "max_activity_modifier_down must be less than or equal to max_activity_modifier_up.",
            })


class MarketActivityModifier(UuidModel):
    city = models.ForeignKey(City, on_delete=models.CASCADE, null=True, blank=True, related_name="activity_modifiers")
    item_id = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=EconomicCategory.choices)
    buy_quantity = models.BigIntegerField(default=0, validators=[MinValueValidator(0)])
    sell_quantity = models.BigIntegerField(default=0, validators=[MinValueValidator(0)])
    buy_transaction_count = models.PositiveIntegerField(default=0)
    sell_transaction_count = models.PositiveIntegerField(default=0)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    activity_modifier = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("1.0000"))
    calculation_version = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "market_activity_modifiers"
        ordering = ["-period_end", "item_id"]

    def clean(self):
        if self.period_end <= self.period_start:
            raise ValidationError({"period_end": "period_end must be after period_start."})


class PriceCalculationRun(UuidModel):
    SOURCE_CHOICES = (("WEBSITE", "Website"), ("MINECRAFT_COMMAND", "Minecraft command"), ("SYSTEM", "System"))
    STATUS_CHOICES = (("SUCCESS", "Success"), ("FAILED", "Failed"))

    triggered_by = models.CharField(max_length=255)
    trigger_source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    calculation_version = models.CharField(max_length=64, unique=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    details = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "price_calculation_runs"
        ordering = ["-started_at"]


class TemporaryMarketModifier(UuidModel):
    city = models.ForeignKey(City, on_delete=models.CASCADE, null=True, blank=True, related_name="temporary_market_modifiers")
    category = models.CharField(max_length=32, choices=EconomicCategory.choices, null=True, blank=True)
    item_id = models.CharField(max_length=255, null=True, blank=True)
    modifier = models.DecimalField(max_digits=8, decimal_places=4, validators=[MinValueValidator(Decimal("0"))])
    reason = models.TextField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "temporary_market_modifiers"

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "ends_at must be after starts_at."})
