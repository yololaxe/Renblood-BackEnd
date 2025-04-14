from django.urls import re_path
from consumers import DiceConsumer

websocket_urlpatterns = [
    re_path(r'ws/dice/$', DiceConsumer.as_asgi()),
]
