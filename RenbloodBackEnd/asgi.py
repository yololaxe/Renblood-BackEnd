import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import routing  # ou players.routing selon où tu as mis DiceConsumer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RenbloodBackEnd.settings")
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(
        routing.websocket_urlpatterns
    ),
})
