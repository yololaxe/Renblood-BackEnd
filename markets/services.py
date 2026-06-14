import hashlib
import logging
import re
import time
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from pymongo import UpdateOne
from rest_framework.exceptions import ValidationError

from .models import (
    CalculatedMarketPrice, City, CityMarketModifier, CounterCreatedSource,
    MarketActivityModifier, MarketEconomyConfig, MarketItemReference,
    MarketModerationLog, MarketTransaction, MarketType, MarketTypeConfig,
    MarketWithdrawal, MerchantCounter, MerchantCounterItem, ModerationStatus,
    OwnerType, PriceCalculationRun, StockMode, TemporaryMarketModifier,
    new_id,
)


ONE = Decimal("1")
logger = logging.getLogger(__name__)


def _decimal(value):
    if isinstance(value, Decimal):
        return value
    if hasattr(value, "to_decimal"):
        return value.to_decimal()
    return Decimal(str(value))


def _unordered(model):
    return list(model.objects.all().order_by())


def _next_calculation_version(now, runs):
    prefix = now.strftime("%Y-%m-%d")
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d{{3}})$")
    sequence = max(
        (int(match.group(1)) for run in runs if (match := pattern.match(run.calculation_version))),
        default=0,
    )
    return f"{prefix}-{sequence + 1:03d}"


def _persist_current_prices(price_rows, version):
    connection.ensure_connection()
    collection = connection.connection[CalculatedMarketPrice._meta.db_table]
    operations = [
        UpdateOne(
            {
                "city_id": row["city_id"],
                "market_type": row["market_type"],
                "item_id": row["item_id"],
            },
            {
                "$set": {
                    "category": row["category"],
                    "calculated_price": row["calculated_price"],
                    "buy_price": row["buy_price"],
                    "sell_price": row["sell_price"],
                    "calculation_version": version,
                    "calculated_at": row["calculated_at"],
                },
                "$setOnInsert": {"id": new_id()},
            },
            upsert=True,
        )
        for row in price_rows
    ]
    if operations:
        collection.bulk_write(operations, ordered=False)
    collection.delete_many({"calculation_version": {"$ne": version}})


def _stable_random(version, city_id, market_type, item_id):
    seed = f"{version}:{city_id}:{market_type}:{item_id}".encode("utf-8")
    ratio = int(hashlib.sha256(seed).hexdigest()[:12], 16) / float(0xFFFFFFFFFFFF)
    return Decimal(str(0.95 + ratio * 0.10))


def _round_price(value):
    return max(1, int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def _temporary_multiplier(city, item, now, modifiers):
    multiplier = ONE
    for modifier in modifiers:
        if not modifier.active or modifier.starts_at > now or modifier.ends_at < now:
            continue
        if modifier.city_id and modifier.city_id != city.id:
            continue
        if modifier.category and modifier.category != item.category:
            continue
        if modifier.item_id and modifier.item_id != item.item_id:
            continue
        multiplier *= _decimal(modifier.modifier)
    return multiplier


def _bounded_price(item, value):
    price = max(1, _round_price(value), item.min_price)
    return min(price, item.max_price) if item.max_price is not None else price


def _enforce_shop_city_order(prices, items):
    for item in items:
        shop_key = (MarketType.SHOP, item.item_id)
        city_key = (MarketType.CITY_MARKET, item.item_id)
        if shop_key in prices and city_key in prices:
            prices[city_key] = max(prices[city_key], prices[shop_key])


def get_economy_config():
    config = MarketEconomyConfig.objects.first()
    if config:
        return config
    return MarketEconomyConfig(
        dynamic_economy_enabled=False,
        activity_window_days=7,
        max_activity_modifier_up=Decimal("1.1500"),
        max_activity_modifier_down=Decimal("0.8500"),
        min_transactions_for_impact=10,
        buy_pressure_weight=Decimal("0.0100"),
        sell_pressure_weight=Decimal("0.0100"),
    )


def _activity_key(city_id, item_id):
    return f"{city_id or 'GLOBAL'}::{item_id}"


def compute_counter_risk(counter, items=None, transactions=None):
    items = list(items if items is not None else counter.items.all())
    transactions = list(transactions if transactions is not None else counter.transactions.all())
    indicators = []
    score = Decimal("0")

    if not counter.city_id:
        indicators.append({"code": "NO_CITY", "severity": "medium", "message": "Counter has no city."})
        score += Decimal("15")
    if len(items) > 50:
        indicators.append({"code": "MANY_ITEMS", "severity": "medium", "message": "Counter has many listed items."})
        score += Decimal("10")
    if counter.last_transaction_at and (timezone.now() - counter.last_transaction_at).days > 30:
        indicators.append({"code": "INACTIVE_LONG", "severity": "low", "message": "Counter has been inactive for a long time."})
        score += Decimal("5")

    recent_cutoff = timezone.now() - timezone.timedelta(hours=1)
    recent_transactions = [t for t in transactions if t.created_at >= recent_cutoff]
    if len(recent_transactions) >= 20:
        indicators.append({"code": "HIGH_FREQUENCY", "severity": "high", "message": "Many transactions in a short period."})
        score += Decimal("25")

    total_gain = sum((t.owner_gain or 0) for t in transactions)
    if total_gain >= 100000:
        indicators.append({"code": "HIGH_OWNER_GAIN", "severity": "medium", "message": "Owner gains are unusually high."})
        score += Decimal("15")

    known_item_ids = {item.item_id for item in MarketItemReference.objects.filter(enabled=True)}
    unknown_items = [item for item in items if item.item_id not in known_item_ids]
    if unknown_items:
        indicators.append({"code": "UNKNOWN_ITEM", "severity": "high", "message": "Counter lists unknown items."})
        score += Decimal("20")

    expensive_manual_items = [item for item in items if (item.manual_buy_price or 0) >= 100000 or (item.manual_sell_price or 0) >= 100000]
    if expensive_manual_items:
        indicators.append({"code": "VERY_HIGH_PRICE", "severity": "medium", "message": "Counter contains very high manual prices."})
        score += Decimal("15")

    return float(min(score, Decimal("100"))), indicators


def refresh_counter_risk(counter, items=None, transactions=None, save=True):
    risk_score, _ = compute_counter_risk(counter, items=items, transactions=transactions)
    counter.risk_score = risk_score
    if save and getattr(counter, "pk", None):
        counter.save(update_fields=["risk_score", "updated_at"])
    return risk_score


def log_counter_moderation(counter, action, new_status, performed_by=None, reason=None, previous_status=None):
    return MarketModerationLog.objects.create(
        counter=counter,
        action=action,
        reason=reason,
        performed_by=performed_by,
        previous_status=previous_status or counter.moderation_status,
        new_status=new_status,
    )


def set_counter_moderation(counter, status_value, performed_by=None, reason=None):
    previous_status = counter.moderation_status
    counter.moderation_status = status_value
    if status_value == ModerationStatus.DISABLED:
        counter.active = False
        counter.moderation_reason = reason
        counter.disabled_by = performed_by
        counter.disabled_at = timezone.now()
    elif status_value == ModerationStatus.ACTIVE:
        counter.active = True
        counter.moderation_reason = None
        counter.disabled_by = None
        counter.disabled_at = None
        counter.flagged_reason = None
    elif status_value == ModerationStatus.FLAGGED:
        counter.flagged_reason = reason
    counter.save(update_fields=[
        "moderation_status", "active", "moderation_reason", "disabled_by",
        "disabled_at", "flagged_reason", "updated_at",
    ])
    action = {
        ModerationStatus.DISABLED: "DISABLED",
        ModerationStatus.ACTIVE: "ENABLED",
        ModerationStatus.FLAGGED: "FLAGGED",
    }.get(status_value, "STATUS_SYNC")
    log_counter_moderation(
        counter,
        action=action,
        new_status=status_value,
        performed_by=performed_by,
        reason=reason,
        previous_status=previous_status,
    )
    return counter


def summarize_activity(window_days=None):
    config = get_economy_config()
    days = window_days or config.activity_window_days
    period_end = timezone.now()
    period_start = period_end - timezone.timedelta(days=days)
    transactions = [
        transaction
        for transaction in _unordered(MarketTransaction)
        if transaction.created_at >= period_start and transaction.created_at <= period_end
    ]
    grouped = defaultdict(lambda: {
        "city": None,
        "item_id": None,
        "category": None,
        "buy_quantity": 0,
        "sell_quantity": 0,
        "buy_transaction_count": 0,
        "sell_transaction_count": 0,
        "period_start": period_start,
        "period_end": period_end,
    })
    references = {item.item_id: item for item in _unordered(MarketItemReference)}
    for transaction in transactions:
        key = _activity_key(transaction.city_id, transaction.item_id)
        bucket = grouped[key]
        bucket["city"] = transaction.city
        bucket["item_id"] = transaction.item_id
        reference = references.get(transaction.item_id)
        bucket["category"] = reference.category if reference else "OTHER"
        if transaction.action == "BUY":
            bucket["buy_quantity"] += transaction.quantity
            bucket["buy_transaction_count"] += 1
        else:
            bucket["sell_quantity"] += transaction.quantity
            bucket["sell_transaction_count"] += 1
    return list(grouped.values()), config


def _compute_activity_modifier_from_bucket(bucket, config):
    total_transactions = bucket["buy_transaction_count"] + bucket["sell_transaction_count"]
    if total_transactions < config.min_transactions_for_impact:
        return Decimal("1.0000")
    increase = _decimal(bucket["buy_quantity"]) * _decimal(config.buy_pressure_weight)
    decrease = _decimal(bucket["sell_quantity"]) * _decimal(config.sell_pressure_weight)
    raw = Decimal("1.0000") + increase - decrease
    return min(_decimal(config.max_activity_modifier_up), max(_decimal(config.max_activity_modifier_down), raw))


def recompute_activity_modifiers(triggered_by="system", calculation_version=None, window_days=None):
    buckets, config = summarize_activity(window_days=window_days)
    period_start = None
    period_end = None
    created = []
    if calculation_version:
        MarketActivityModifier.objects.filter(calculation_version=calculation_version).delete()
    else:
        MarketActivityModifier.objects.filter(calculation_version__isnull=True).delete()
    for bucket in buckets:
        period_start = bucket["period_start"]
        period_end = bucket["period_end"]
        modifier = _compute_activity_modifier_from_bucket(bucket, config)
        created.append(MarketActivityModifier.objects.create(
            city=bucket["city"],
            item_id=bucket["item_id"],
            category=bucket["category"] or "OTHER",
            buy_quantity=bucket["buy_quantity"],
            sell_quantity=bucket["sell_quantity"],
            buy_transaction_count=bucket["buy_transaction_count"],
            sell_transaction_count=bucket["sell_transaction_count"],
            period_start=bucket["period_start"],
            period_end=bucket["period_end"],
            activity_modifier=modifier,
            calculation_version=calculation_version,
        ))
    logger.info(
        "Market activity recomputed modifiers=%s window_days=%s dynamic_enabled=%s triggered_by=%s calculation_version=%s",
        len(created),
        config.activity_window_days if window_days is None else window_days,
        config.dynamic_economy_enabled,
        triggered_by,
        calculation_version,
    )
    return {
        "periodStart": period_start,
        "periodEnd": period_end,
        "windowDays": config.activity_window_days if window_days is None else window_days,
        "dynamicEconomyEnabled": config.dynamic_economy_enabled,
        "modifiers": created,
    }


def recalculate_prices(triggered_by, trigger_source):
    started_clock = time.monotonic()
    now = timezone.now()
    runs = _unordered(PriceCalculationRun)
    version = _next_calculation_version(now, runs)
    economy_config = get_economy_config()
    run = PriceCalculationRun.objects.create(
        triggered_by=triggered_by,
        trigger_source=trigger_source,
        status="FAILED",
        calculation_version=version,
        started_at=now,
    )
    logger.info("Market price calculation started version=%s source=%s triggered_by=%s", version, trigger_source, triggered_by)
    try:
        items = [item for item in _unordered(MarketItemReference) if item.enabled]
        cities = [city for city in _unordered(City) if city.active]
        configs = [config for config in _unordered(MarketTypeConfig) if config.active]
        city_modifiers = {
            (modifier.city_id, modifier.category): _decimal(modifier.modifier)
            for modifier in _unordered(CityMarketModifier)
            if modifier.active
        }
        temporary_modifiers = _unordered(TemporaryMarketModifier)
        activity_rows = []
        activity_modifier_map = {}
        if economy_config.dynamic_economy_enabled:
            activity_result = recompute_activity_modifiers(
                triggered_by=triggered_by,
                calculation_version=version,
                window_days=economy_config.activity_window_days,
            )
            activity_rows = activity_result["modifiers"]
            activity_modifier_map = {
                (modifier.city_id, modifier.item_id): _decimal(modifier.activity_modifier)
                for modifier in activity_rows
            }
        calculated_at = timezone.now()
        price_rows = []
        for city in cities:
            prices_for_city = {}
            for config in configs:
                for item in items:
                    activity_modifier = activity_modifier_map.get((city.id, item.item_id), Decimal("1.0000"))
                    value = (
                        _decimal(item.reference_price)
                        * city_modifiers.get((city.id, item.category), ONE)
                        * _decimal(config.base_modifier)
                        * _temporary_multiplier(city, item, calculated_at, temporary_modifiers)
                        * _stable_random(version, city.id, config.type, item.item_id)
                        * (ONE + _decimal(config.tax_rate))
                        * activity_modifier
                    )
                    price = _bounded_price(item, value)
                    prices_for_city[(config.type, item.item_id)] = price

            _enforce_shop_city_order(prices_for_city, items)

            for config in configs:
                for item in items:
                    price = prices_for_city[(config.type, item.item_id)]
                    price_rows.append({
                        "city_id": city.id,
                        "market_type": config.type,
                        "item_id": item.item_id,
                        "category": item.category,
                        "calculated_price": price,
                        "buy_price": price,
                        "sell_price": price,
                        "calculated_at": calculated_at,
                    })

        _persist_current_prices(price_rows, version)
        count = len(price_rows)

        details = {
            "citiesProcessed": len(cities),
            "itemsProcessed": len(items),
            "marketTypesProcessed": len(configs),
            "pricesGenerated": count,
            "dynamicEconomyEnabled": economy_config.dynamic_economy_enabled,
            "activityModifiersApplied": len(activity_rows),
        }
        run.status = "SUCCESS"
        run.finished_at = timezone.now()
        run.details = (
            f"{count} prices calculated for {len(cities)} cities, "
            f"{len(items)} items and {len(configs)} market types. "
            f"Dynamic economy={'on' if economy_config.dynamic_economy_enabled else 'off'}; "
            f"activity modifiers={len(activity_rows)}."
        )
        run.save(update_fields=["status", "finished_at", "details"])
        logger.info(
            "Market price calculation succeeded version=%s prices=%s duration_ms=%s",
            version, count, round((time.monotonic() - started_clock) * 1000),
        )
        return {
            "status": "success",
            "calculationVersion": version,
            **details,
            "calculatedAt": calculated_at,
            "run": run,
        }
    except Exception as exc:
        run.finished_at = timezone.now()
        run.details = str(exc)
        run.save(update_fields=["finished_at", "details"])
        logger.exception("Market price calculation failed version=%s", version)
        raise


def resolve_counter_item_price(counter_item, action):
    if not counter_item.auto_price:
        price = counter_item.manual_buy_price if action == "BUY" else counter_item.manual_sell_price
    else:
        if not counter_item.counter.city_id:
            raise ValidationError("An auto-priced counter requires a city.")
        try:
            current = CalculatedMarketPrice.objects.get(
                city_id=counter_item.counter.city_id,
                market_type=counter_item.counter.type,
                item_id=counter_item.item_id,
            )
        except CalculatedMarketPrice.DoesNotExist as exc:
            raise ValidationError("No calculated price exists for this counter item.") from exc
        price = current.buy_price if action == "BUY" else current.sell_price
        price = _round_price(_decimal(price) * _decimal(counter_item.local_modifier))
    if price is None:
        raise ValidationError("No price is configured for this action.")
    return max(1, int(price))


@transaction.atomic
def record_transaction(validated_data):
    counter = validated_data["counter"]
    action = validated_data["action"]
    quantity = validated_data["quantity"]
    try:
        counter_item = MerchantCounterItem.objects.get(
            counter=counter, item_id=validated_data["item_id"], active=True,
        )
    except MerchantCounterItem.DoesNotExist as exc:
        raise ValidationError({"item_id": "This item is not active in the counter."}) from exc

    if not counter.active:
        logger.warning(
            "Rejected transaction on inactive counter counter_id=%s moderation_status=%s action=%s player_uuid=%s",
            counter.counter_id,
            counter.moderation_status,
            action,
            validated_data["player_uuid"],
        )
        raise ValidationError("Counter is inactive.")
    if counter.moderation_status == ModerationStatus.DISABLED:
        logger.warning(
            "Rejected transaction on disabled counter counter_id=%s action=%s player_uuid=%s",
            counter.counter_id,
            action,
            validated_data["player_uuid"],
        )
        raise ValidationError("Counter is disabled by moderation.")
    if action == "BUY" and (not counter.buy_mode_enabled or not counter_item.buy_enabled):
        raise ValidationError("Buying is disabled for this item.")
    if action == "SELL" and (not counter.sell_mode_enabled or not counter_item.sell_enabled):
        raise ValidationError("Selling is disabled for this item.")

    unit_price = resolve_counter_item_price(counter_item, action)
    total_price = unit_price * quantity
    supplied_unit_price = validated_data.get("unit_price")
    supplied_total_price = validated_data.get("total_price")
    if supplied_unit_price is not None and supplied_unit_price != unit_price:
        raise ValidationError({"unitPrice": f"unitPrice must match the current counter price ({unit_price})."})
    if supplied_total_price is not None and supplied_total_price != total_price:
        raise ValidationError({"totalPrice": "totalPrice must equal quantity multiplied by the current counter price."})
    owner_gain = total_price if action == "BUY" else 0
    supplied_owner_gain = validated_data.get("owner_gain")
    if supplied_owner_gain is not None and supplied_owner_gain != owner_gain:
        raise ValidationError({"ownerGain": f"ownerGain must be {owner_gain} for this transaction."})

    if counter_item.stock_mode == StockMode.LIMITED:
        current_stock = counter_item.stock_quantity or 0
        if action == "BUY" and current_stock < quantity:
            raise ValidationError({"quantity": "Insufficient stock."})
        counter_item.stock_quantity = current_stock - quantity if action == "BUY" else current_stock + quantity
        counter_item.save(update_fields=["stock_quantity", "updated_at"])

    transaction_record = MarketTransaction.objects.create(
        counter=counter,
        city=counter.city,
        player_uuid=validated_data["player_uuid"],
        player_name=validated_data["player_name"],
        owner_type=counter.owner_type,
        owner_id=counter.owner_id,
        item_id=counter_item.item_id,
        item_display_name=counter_item.display_name,
        action=action,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
        owner_gain=owner_gain,
    )
    counter.last_transaction_at = transaction_record.created_at
    refresh_counter_risk(counter, transactions=list(counter.transactions.all()), save=False)
    counter.save(update_fields=["last_transaction_at", "risk_score", "updated_at"])
    return transaction_record
