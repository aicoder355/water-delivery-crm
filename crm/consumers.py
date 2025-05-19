import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

class DriverNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_authenticated and hasattr(user, 'driver_profile'):
            self.driver_id = user.driver_profile.id
            self.group_name = f'driver_{self.driver_id}'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Водителю не нужно отправлять сообщения
        pass

    async def send_notification(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
        }))
