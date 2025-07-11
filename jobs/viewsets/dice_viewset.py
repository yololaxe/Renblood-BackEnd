import json
import random
from channels.generic.websocket import AsyncWebsocketConsumer

class DiceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("dice_room", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dice_room", self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get("type") == "roll":
            # récupère min/max/mod, avec valeurs par défaut
            min_val = int(data.get("min", 1))
            max_val = int(data.get("max", 20))
            mod     = int(data.get("mod", 0))

            # tire entre min et max puis ajoute le mod
            result = random.randint(min_val, max_val) + mod

            # broadcast à tout le monde dans le groupe
            await self.channel_layer.group_send(
                "dice_room",
                {
                    "type": "dice_rolled",
                    "value": result,
                }
            )

    async def dice_rolled(self, event):
        # envoi au client avec le bon type pour la UI
        await self.send(text_data=json.dumps({
            "type": "dice_result",
            "value": event["value"],
        }))
