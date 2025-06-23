import os
import threading

from django.apps import AppConfig
from django.db.models.signals import post_migrate

class PlayersConfig(AppConfig):
    default_auto_field = 'djongo.models.ObjectIdField'
    name = 'players'

    def ready(self):
        post_migrate.disconnect(sender=self)
        from django.core.management import get_commands
        if 'runserver' in get_commands() or os.environ.get('ASGI_WORKER'):
                from presence_bot import run_presence_bot
                threading.Thread(target=run_presence_bot, daemon=True).start()