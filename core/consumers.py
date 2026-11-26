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


class VideoCallConsumer(AsyncWebsocketConsumer):
    """
    Authenticated WebRTC signaling + in-call chat consumer for video appointments.
    Zero external paid video API or card required.
    """

    async def connect(self):
        self.appointment_id = self.scope['url_route']['kwargs']['appointment_id']
        self.group_name = f'video_{self.appointment_id}'
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        auth_info = await self._authorize_participant(user.id)
        if not auth_info:
            await self.close(code=4403)
            return

        self.role = auth_info['role']
        self.display_name = auth_info['display_name']

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'role'):
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'signal_relay',
                    'sender_channel': self.channel_name,
                    'payload': {
                        'type': 'peer_left',
                        'role': self.role,
                        'name': self.display_name,
                    },
                },
            )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (ValueError, TypeError):
            return

        msg_type = data.get('type')
        allowed_signal_types = {'ready', 'patient_waiting', 'offer', 'answer', 'ice_candidate'}

        if msg_type in allowed_signal_types:
            payload = dict(data)
            payload['role'] = self.role
            payload['name'] = self.display_name
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'signal_relay',
                    'sender_channel': self.channel_name,
                    'payload': payload,
                },
            )
        elif msg_type == 'chat':
            text = (data.get('message') or '').strip()
            if not text:
                return
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'signal_relay',
                    'sender_channel': None,  # deliver to both peers
                    'payload': {
                        'type': 'chat',
                        'sender': self.display_name,
                        'role': self.role,
                        'message': text[:1000],
                        'time': timezone.localtime().strftime('%I:%M %p'),
                    },
                },
            )

    async def signal_relay(self, event):
        if event.get('sender_channel') == self.channel_name:
            return
        await self.send(text_data=json.dumps(event['payload']))

    async def call_ended(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call_ended',
            'message': event.get('message', 'The doctor has ended this consultation.'),
        }))

    @database_sync_to_async
    def _authorize_participant(self, user_id):
        from core.models import Appointment
        from core.video_utils import get_appointment_window

        appt = (
            Appointment.objects.select_related('patient__user', 'slot', 'slot__doctor__user')
            .filter(pk=self.appointment_id)
            .first()
        )
        if not appt or appt.appointment_type != 'video':
            return None
        if appt.status not in ('confirmed', 'accepted'):
            return None
        win = get_appointment_window(appt)
        if not win['is_session_active']:
            return None

        if appt.slot.doctor.user_id == user_id:
            return {'role': 'doctor', 'display_name': f'Dr. {appt.slot.doctor.name}'}
        if appt.patient.user_id == user_id:
            return {'role': 'patient', 'display_name': appt.patient.name}
        return None
