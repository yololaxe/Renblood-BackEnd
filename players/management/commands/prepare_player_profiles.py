from django.core.management.base import BaseCommand
from economy.store import get_bank


class Command(BaseCommand):
    help = "Prépare les index des nouveaux dossiers d'inscription, sans modifier les personnages existants."

    def handle(self, *args, **options):
        db = get_bank().db
        db.player_registration_profiles.create_index([("status", 1), ("_id", 1)])
        db.player_registration_link_codes.create_index("code_hash", unique=True)
        db.player_registration_link_codes.create_index("purge_at", expireAfterSeconds=0)
        db.player_registration_attempts.create_index("purge_at", expireAfterSeconds=0)
        db.player_registration_links.create_index("owner_id")
        self.stdout.write(self.style.SUCCESS("Index des dossiers prêts ; aucun personnage modifié."))
