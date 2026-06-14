from django.db import migrations


DEFAULT_CONFIGS = [
    ("SHOP", "Boutique", "1.0000", "Official or owner-operated shop"),
    ("CITY_MARKET", "Marche de ville", "1.0500", "City market, slightly more expensive than shops"),
    ("TEMPORARY_MARKET", "Marche temporaire", "1.0000", "Temporary event market"),
    ("GUILD_COUNTER", "Comptoir de guilde", "1.0000", "Guild-operated counter"),
    ("PLAYER_MARKET", "Comptoir prive", "1.0000", "Player-operated private market"),
]


def seed_configs(apps, schema_editor):
    MarketTypeConfig = apps.get_model("markets", "MarketTypeConfig")
    for market_type, display_name, base_modifier, description in DEFAULT_CONFIGS:
        MarketTypeConfig.objects.get_or_create(
            type=market_type,
            defaults={
                "display_name": display_name,
                "base_modifier": base_modifier,
                "tax_rate": "0.0000",
                "active": True,
                "description": description,
            },
        )


def remove_seeded_configs(apps, schema_editor):
    MarketTypeConfig = apps.get_model("markets", "MarketTypeConfig")
    MarketTypeConfig.objects.filter(type__in=[config[0] for config in DEFAULT_CONFIGS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0002_merchantcounteritem_category_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_configs, remove_seeded_configs),
    ]
