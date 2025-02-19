from django.apps import AppConfig
from django.db.models.signals import post_migrate

class PlayersConfig(AppConfig):
    default_auto_field = 'djongo.models.ObjectIdField'
    name = 'players'

    def ready(self):
        post_migrate.disconnect(sender=self)
