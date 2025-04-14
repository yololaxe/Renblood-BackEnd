import json
from channels.generic.websocket import AsyncWebsocketConsumer

class DiceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("dice_room", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dice_room", self.channel_name)

    async def dice_rolled(self, event):
        await self.send(text_data=json.dumps({
            'type': 'dice_result',
            'value': event['value']
        }))
