from decimal import Decimal

from django.core.management.base import BaseCommand

from markets.models import (
    City, CityMarketModifier, EconomicCategory, MarketCategory,
    MarketItemReference, MarketTypeConfig,
)


CITIES = [
    "Circos", "Rozdru", "Lead Peaks", "Mytiya", "Aasari", "Freezing Farm",
    "Kilkou", "The Verdict", "Moria", "Fyvelune", "Saint Troufion de Paumé",
    "Valentine", "Saint Aquillon", "Evonia", "Creed", "Altkrirch", "Triomphe",
    "Isvanore", "Lone", "Sylinore", "Ages", "Shaleton", "Bransby Horses",
]

CATEGORIES = [choice[0] for choice in EconomicCategory.choices]

MARKET_TYPES = {
    "SHOP": ("Boutique", "0.90"),
    "CITY_MARKET": ("Marché de ville", "1.00"),
    "TEMPORARY_MARKET": ("Marché temporaire", "1.10"),
    "GUILD_COUNTER": ("Comptoir de guilde", "0.95"),
    "PLAYER_MARKET": ("Comptoir joueur", "1.00"),
}

REFERENCE_ITEMS = {
    "minecraft:bread": ("Pain", "FOOD", 64),
    "minecraft:iron_ingot": ("Lingot de fer", "IRON", 320),
    "minecraft:oak_log": ("Bûche de chêne", "WOOD", 32),
    "minecraft:cobblestone": ("Pierre taillée", "STONE", 8),
    "minecraft:wheat": ("Blé", "FARMING", 24),
    "minecraft:stick": ("Bâton", "WOOD", 4),
    "minecraft:stone_pickaxe": ("Pioche en pierre", "TOOLS", 96),
    "minecraft:iron_sword": ("Épée en fer", "WEAPONS", 768),
}

BASE_MODIFIER_CATEGORIES = [
    "FOOD", "WOOD", "STONE", "IRON", "FARMING",
    "TOOLS", "WEAPONS", "CONSTRUCTION", "OTHER",
]

CITY_VARIATIONS = {
    "Circos": {"FOOD": "1.00", "WOOD": "1.05", "IRON": "1.00", "STONE": "1.00"},
    "Rozdru": {"FOOD": "1.05", "WOOD": "0.95", "IRON": "1.10", "STONE": "0.95"},
    "Lead Peaks": {"FOOD": "1.10", "WOOD": "1.05", "IRON": "0.85", "STONE": "0.90"},
    "Mytiya": {"FOOD": "0.95", "WOOD": "1.00", "IRON": "1.05", "STONE": "1.00"},
    "Aasari": {"FOOD": "0.95", "WOOD": "1.10", "IRON": "1.10", "STONE": "1.00"},
    "Freezing Farm": {"FOOD": "0.85", "WOOD": "1.15", "IRON": "1.15", "STONE": "1.05", "FARMING": "0.85"},
    "Kilkou": {"FOOD": "1.00", "WOOD": "0.90", "IRON": "1.05", "STONE": "1.00"},
    "The Verdict": {"FOOD": "1.15", "WOOD": "1.10", "IRON": "1.05", "STONE": "1.00", "WEAPONS": "0.95"},
    "Moria": {"FOOD": "1.15", "WOOD": "1.10", "IRON": "0.80", "STONE": "0.85", "TOOLS": "0.95"},
    "Fyvelune": {"FOOD": "0.95", "WOOD": "1.00", "IRON": "1.10", "STONE": "1.00", "LUXURY": "0.95"},
    "Saint Troufion de Paumé": {"FOOD": "1.10", "WOOD": "0.95", "IRON": "1.20", "STONE": "1.05"},
    "Valentine": {"FOOD": "0.95", "WOOD": "1.00", "IRON": "1.05", "STONE": "1.00", "FARMING": "0.90"},
    "Saint Aquillon": {"FOOD": "1.05", "WOOD": "1.10", "IRON": "1.05", "STONE": "0.95"},
    "Evonia": {"FOOD": "1.00", "WOOD": "1.00", "IRON": "1.00", "STONE": "1.00"},
    "Creed": {"FOOD": "1.05", "WOOD": "1.00", "IRON": "0.95", "STONE": "1.00", "WEAPONS": "0.95"},
    "Altkrirch": {"FOOD": "1.00", "WOOD": "1.05", "IRON": "0.95", "STONE": "0.95", "CONSTRUCTION": "0.95"},
    "Triomphe": {"FOOD": "1.05", "WOOD": "1.05", "IRON": "1.00", "STONE": "1.00", "LUXURY": "0.90", "WEAPONS": "0.95"},
    "Isvanore": {"FOOD": "1.00", "WOOD": "1.10", "IRON": "0.95", "STONE": "1.00"},
    "Lone": {"FOOD": "0.90", "WOOD": "1.00", "IRON": "1.20", "STONE": "1.00"},
    "Sylinore": {"FOOD": "0.95", "WOOD": "0.95", "IRON": "1.10", "STONE": "1.00"},
    "Ages": {"FOOD": "1.00", "WOOD": "1.05", "IRON": "1.05", "STONE": "0.95"},
    "Shaleton": {"FOOD": "1.05", "WOOD": "0.90", "IRON": "1.10", "STONE": "1.00"},
    "Bransby Horses": {"FOOD": "0.95", "WOOD": "1.00", "IRON": "1.10", "STONE": "1.00", "FARMING": "0.90"},
}


def _unordered(model):
    return list(model.objects.all().order_by())


def _apply(instance, values):
    changed = []
    for field, value in values.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed.append(field)
    if changed:
        instance.save(update_fields=changed)


def seed_markets():
    summary = {
        "cities_created": 0, "cities_existing": 0,
        "categories_created": 0, "categories_existing": 0,
        "types_created": 0, "types_existing": 0,
        "items_created": 0, "items_existing": 0,
        "modifiers_created": 0, "modifiers_existing": 0,
    }

    cities = {city.name: city for city in _unordered(City)}
    for name in CITIES:
        if name in cities:
            summary["cities_existing"] += 1
            _apply(cities[name], {"active": True})
        else:
            cities[name] = City.objects.create(name=name, active=True)
            summary["cities_created"] += 1

    categories = {category.code: category for category in _unordered(MarketCategory)}
    category_labels = dict(EconomicCategory.choices)
    for code in CATEGORIES:
        values = {"display_name": category_labels[code], "active": True}
        if code in categories:
            summary["categories_existing"] += 1
            _apply(categories[code], values)
        else:
            categories[code] = MarketCategory.objects.create(code=code, **values)
            summary["categories_created"] += 1

    market_types = {config.type: config for config in _unordered(MarketTypeConfig)}
    for market_type, (display_name, base_modifier) in MARKET_TYPES.items():
        values = {
            "display_name": display_name,
            "base_modifier": Decimal(base_modifier),
            "tax_rate": Decimal("0.00"),
            "active": True,
        }
        if market_type in market_types:
            summary["types_existing"] += 1
            _apply(market_types[market_type], values)
        else:
            market_types[market_type] = MarketTypeConfig.objects.create(type=market_type, **values)
            summary["types_created"] += 1

    items = {item.item_id: item for item in _unordered(MarketItemReference)}
    for item_id, (display_name, category, price) in REFERENCE_ITEMS.items():
        values = {
            "display_name": display_name,
            "category": category,
            "reference_price": price,
            "reference_xp": 0,
            "min_price": 1,
            "max_price": None,
            "enabled": True,
        }
        if item_id in items:
            summary["items_existing"] += 1
            _apply(items[item_id], values)
        else:
            items[item_id] = MarketItemReference.objects.create(item_id=item_id, **values)
            summary["items_created"] += 1

    modifiers = {
        (modifier.city_id, modifier.category): modifier
        for modifier in _unordered(CityMarketModifier)
    }
    for city_name in CITIES:
        city = cities[city_name]
        category_values = {category: "1.00" for category in BASE_MODIFIER_CATEGORIES}
        category_values.update(CITY_VARIATIONS.get(city_name, {}))
        for category, modifier in category_values.items():
            key = (city.id, category)
            values = {
                "modifier": Decimal(modifier),
                "active": True,
                "reason": "Modificateur économique initial Renblood",
            }
            if key in modifiers:
                summary["modifiers_existing"] += 1
                _apply(modifiers[key], values)
            else:
                modifiers[key] = CityMarketModifier.objects.create(city=city, category=category, **values)
                summary["modifiers_created"] += 1

    return summary


class Command(BaseCommand):
    help = "Initialise les données de base du système Comptoir marchand."

    def handle(self, *args, **options):
        summary = seed_markets()
        self.stdout.write(self.style.SUCCESS("Seed Comptoir marchand terminé."))
        labels = [
            ("Villes créées", "cities_created"),
            ("Villes déjà existantes", "cities_existing"),
            ("Catégories créées", "categories_created"),
            ("Catégories déjà existantes", "categories_existing"),
            ("Types de comptoirs créés", "types_created"),
            ("Types de comptoirs déjà existants", "types_existing"),
            ("Items créés", "items_created"),
            ("Items déjà existants", "items_existing"),
            ("Modificateurs créés", "modifiers_created"),
            ("Modificateurs déjà existants", "modifiers_existing"),
        ]
        for label, key in labels:
            self.stdout.write(f"- {label} : {summary[key]}")
