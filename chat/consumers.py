import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return

        self.room_id = self.scope['url_route']['kwargs']['room_id']
        
        # Verify user is participant
        if not await self.is_room_participant():
            await self.close()
            return
            
        self.room_group_name = f'chat_{self.room_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Send previous messages
        await self.send_previous_messages()
        
        # Send online status to room
        await self.update_online_status(True)

    async def disconnect(self, close_code):
        await self.update_online_status(False)
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'message')
        
        if message_type == 'message':
            message = data.get('message', '').strip()
            
            if not message or len(message) > 5000:
                return
                
            # Save message to database
            saved_message = await self.save_message(message)
            
            # Get unread counts for all participants
            unread_counts = await self.get_unread_counts_for_participants()
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': self.user.id,
                    'sender_name': self.user.get_full_name() or self.user.username,
                    'timestamp': saved_message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    'message_id': saved_message.id,
                    'unread_counts': unread_counts
                }
            )
            
        elif message_type == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': self.user.id,
                    'user_name': self.user.get_full_name() or self.user.username,
                    'is_typing': data.get('is_typing', False)
                }
            )
            
        elif message_type == 'read_receipt':
            await self.mark_messages_read(data.get('message_ids', []))
            # Broadcast read receipts to room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'read_receipt',
                    'user_id': self.user.id,
                    'message_ids': data.get('message_ids', [])
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp': event['timestamp'],
            'message_id': event.get('message_id'),
            'unread_counts': event.get('unread_counts', {})
        }))
    
    async def typing_indicator(self, event):
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))
    
    async def read_receipt(self, event):
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'read_receipt',
                'user_id': event['user_id'],
                'message_ids': event['message_ids']
            }))

    async def online_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'online_status',
            'user_id': event['user_id'],
            'is_online': event['is_online']
        }))

    @database_sync_to_async
    def is_room_participant(self):
        return ChatRoom.objects.filter(
            id=self.room_id, 
            participants=self.user
        ).exists()

    @database_sync_to_async
    def save_message(self, content):
        room = ChatRoom.objects.get(id=self.room_id)
        msg = Message.objects.create(
            room=room,
            sender=self.user,
            content=content
        )
        return msg

    async def send_previous_messages(self):
        messages = await self.get_previous_messages()
        for msg in messages:
            await self.send(text_data=json.dumps({
                'type': 'chat_message',
                'message': msg['content'],
                'sender_id': msg['sender_id'],
                'sender_name': msg['sender_name'],
                'timestamp': msg['timestamp'],
                'message_id': msg['message_id'],
                'is_read': msg['is_read']
            }))

    @database_sync_to_async
    def get_previous_messages(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            messages = room.messages.select_related('sender').all()[:50]
            return [{
                'content': msg.content,
                'sender_id': msg.sender.id,
                'sender_name': msg.sender.get_full_name() or msg.sender.username,
                'timestamp': msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                'message_id': msg.id,
                'is_read': msg.is_read
            } for msg in messages]
        except ChatRoom.DoesNotExist:
            return []

    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        messages = Message.objects.filter(
            id__in=message_ids,
            room_id=self.room_id
        ).exclude(sender=self.user)
        
        for message in messages:
            message.mark_as_read(self.user)
        
        return messages.count()

    @database_sync_to_async
    def get_unread_counts_for_participants(self):
        room = ChatRoom.objects.get(id=self.room_id)
        counts = {}
        for participant in room.participants.all():
            count = room.get_unread_count(participant)
            if count > 0:
                counts[participant.id] = count
        return counts

    @database_sync_to_async
    def update_online_status(self, is_online):
        # Store online status in cache or database (implement as needed)
        # For now, broadcast to room
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            self.room_group_name,
            {
                'type': 'online_status',
                'user_id': self.user.id,
                'is_online': is_online
            }
        )