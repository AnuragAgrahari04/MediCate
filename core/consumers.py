import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.consultation_id = self.scope['url_route']['kwargs']['consultation_id']
        self.room_name = f'chat_{self.consultation_id}'
        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type', 'message')

        if msg_type == 'message':
            message = data.get('message', '').strip()
            if not message:
                return
            sender = self.scope['user']
            saved  = await self.save_message(message)
            await self.channel_layer.group_send(self.room_name, {
                'type':      'chat_message',
                'message':   message,
                'sender':    sender.username,
                'timestamp': saved.timestamp.strftime('%b %d, %Y, %I:%M %p'),
                'msg_id':    saved.id,
            })

        elif msg_type == 'typing':
            await self.channel_layer.group_send(self.room_name, {
                'type':   'user_typing',
                'sender': self.scope['user'].username,
            })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':      'message',
            'message':   event['message'],
            'sender':    event['sender'],
            'timestamp': event['timestamp'],
            'msg_id':    event['msg_id'],
        }))

    async def user_typing(self, event):
        if event['sender'] != self.scope['user'].username:
            await self.send(text_data=json.dumps({
                'type':   'typing',
                'sender': event['sender'],
            }))

    @database_sync_to_async
    def save_message(self, message):
        from core.models import Consultation, ChatMessage
        c = Consultation.objects.get(id=self.consultation_id)
        return ChatMessage.objects.create(
            consultation=c,
            sender=self.scope['user'],
            message=message,
        )
