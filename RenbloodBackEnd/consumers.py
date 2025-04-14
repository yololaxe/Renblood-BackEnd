import json
import random
from channels.generic.websocket import AsyncWebsocketConsumer

class DiceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get("type") == "roll":
            result = random.randint(1, 20)
            await self.send(text_data=json.dumps({
                "type": "dice_result",
                "value": result
            }))
