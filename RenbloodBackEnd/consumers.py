import json
import random
from channels.generic.websocket import AsyncWebsocketConsumer

class DiceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("dice", self.channel_name)
        await self.accept()
        print("✅ WebSocket connecté :", self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dice", self.channel_name)
        print("🔴 Déconnecté :", self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get("type") == "roll":
            result = random.randint(1, 20)
            print(f"🎲 Dé lancé : {result}")
            # 🔁 Envoi à tout le groupe "dice"
            await self.channel_layer.group_send(
                "dice",
                {
                    "type": "dice_result",  # déclenche la méthode dice_result()
                    "value": result
                }
            )

    async def dice_result(self, event):
        await self.send(text_data=json.dumps({
            "type": "dice_result",
            "value": event["value"]
        }))
