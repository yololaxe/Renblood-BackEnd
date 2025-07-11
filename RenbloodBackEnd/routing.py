# jobs/routing.py
from django.urls import re_path

from RenbloodBackEnd.consumers import DiceConsumer

websocket_urlpatterns = [
    # correspond à ws://<host>/ws/dice/
    re_path(r'ws/dice/$', DiceConsumer.as_asgi()),
]
