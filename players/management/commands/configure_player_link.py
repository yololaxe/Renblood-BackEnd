"""Provision a server-only proof key. Never prints it or includes it in browser configuration."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import tempfile
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from economy.store import get_bank


class Command(BaseCommand):
    help = "Autorise un profil Minecraft pour les associations vérifiées, sans exposer sa clé au front."

    def add_arguments(self, parser):
        parser.add_argument("--profile", required=True, help="Dossier du profil ou serveur contenant config/medieval_coins/server_config.json")
        parser.add_argument("--label", required=True)
        parser.add_argument("--rotate", action="store_true")

    def handle(self, *args, **options):
        profile = Path(options["profile"]).resolve()
        path = profile / "config/medieval_coins/server_config.json"
        if not path.is_file():
            raise CommandError("Configuration Medieval Coins introuvable dans ce profil.")
        config = json.loads(path.read_text(encoding="utf-8-sig"))
        servers = get_bank().db.player_registration_servers
        server_id = config.get("playerLinkServerId") or str(uuid4())
        key = config.get("playerLinkKey")
        previous = servers.find_one({"_id": server_id})
        if not options["rotate"] and key and previous and previous.get("enabled") and secrets.compare_digest(
                previous["key_hash"], hashlib.sha256(key.encode()).hexdigest()):
            self.stdout.write("Ce profil est déjà autorisé ; sa clé reste inchangée.")
            return
        key = secrets.token_urlsafe(32)
        backup = profile / "renblood-backups" / ("player-link-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(path, backup / path.name)
        config.update(playerLinkServerId=server_id, playerLinkKey=key)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="player-link-", suffix=".tmp", delete=False) as stream:
            stream.write(json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8"))
            temporary = Path(stream.name)
        try:
            temporary.replace(path)
            servers.replace_one({"_id": server_id}, {"_id": server_id, "key_hash": hashlib.sha256(key.encode()).hexdigest(),
                "enabled": True, "label": options["label"][:100], "updated_at": datetime.now().isoformat()}, upsert=True)
        except Exception:
            shutil.copy2(backup / path.name, path)
            raise
        finally:
            temporary.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS("Profil Minecraft autorisé. Clé privée enregistrée dans sa configuration, jamais dans le front."))
