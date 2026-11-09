"""Add only missing reference items; never reset an administrator's catalogue."""
from django.core.management.base import BaseCommand

from markets.models import EconomicCategory, MarketItemReference
from markets.reference_catalog import REFERENCE_ITEMS


def seed_reference_items(*, dry_run=False):
    # Djongo supports an unordered read reliably; avoid one DB query per item.
    existing = {item.item_id for item in MarketItemReference.objects.all().order_by()}
    categories = {choice[0] for choice in EconomicCategory.choices}
    pending = []
    preserved = 0
    for item_id, (display_name, category, price) in REFERENCE_ITEMS.items():
        if category not in categories:
            raise ValueError(f"Unknown economic category: {category}")
        candidate = MarketItemReference(
            item_id=item_id, display_name=display_name, category=category,
            reference_price=price, reference_xp=0, min_price=1,
            max_price=None, enabled=True,
        )
        candidate.full_clean(validate_unique=False)
        if item_id in existing:
            preserved += 1
        else:
            pending.append(candidate)
    # Validate the complete catalogue before making the first write.
    if not dry_run:
        for item in pending:
            item.save(force_insert=True)
    return {"catalogue": len(REFERENCE_ITEMS), "created": 0 if dry_run else len(pending),
            "missing": len(pending), "preserved": preserved, "dry_run": dry_run}


class Command(BaseCommand):
    help = "Ajoute 100 références de prix sans modifier les réglages existants (prix unitaires en fer)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Afficher le bilan sans écrire en base.")


    def handle(self, *args, **options):
        result = seed_reference_items(dry_run=options["dry_run"])
        self.stdout.write(str(result))
