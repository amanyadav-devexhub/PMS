# consumers.py - Update ChatConsumer class

import json
import base64
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from .models import ChatRoom, Message, MessageAttachment
from django.db import transaction
from django.utils import timezone
import os
from PIL import Image
from io import BytesIO

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return

        self.room_id = self.scope['url_route']['kwargs']['room_id']
        
      
        if not await self.is_room_participant():
            await self.close()
            return
            
        self.room_group_name = f'chat_{self.room_id}'
        self.redis_online_key = f'room_{self.room_id}_online_users'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        await self.update_online_status_redis(True)
        
      
        await self.broadcast_online_status(True)

    async def disconnect(self, close_code):
        if hasattr(self, 'user'):
          
            await self.update_online_status_redis(False)
            await self.broadcast_online_status(False)
            
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def update_online_status_redis(self, is_online):
        """Update online status in Redis set"""
        try:
           
            pass
        except Exception:
            pass

    async def broadcast_online_status(self, is_online):
        """Broadcast online status to the room"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'online_status',
                'user_id': self.user.id,
                'is_online': is_online
            }
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = data.get('type', 'message')
        
        if message_type == 'message':
            message_content = data.get('message', '').strip()
            temp_id = data.get('temp_id')
            
            if not message_content or len(message_content) > 5000:
                return
          
            result = await self.save_message_atomic(message_content)
            
            if result['success']:
                saved_message = result['message']
                unread_counts = await self.get_unread_counts_for_participants()
                
              
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message_content,
                        'sender_id': self.user.id,
                        'sender_name': self.user.get_full_name() or self.user.username,
                        'timestamp': saved_message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        'message_id': saved_message.id,
                        'temp_id': temp_id,
                        'unread_counts': unread_counts,
                        'is_read': saved_message.is_read,
                        'read_by': [],
                        'attachments': []
                    }
                )

                await self.broadcast_global_sidebar_update(saved_message, message_content, unread_counts)
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': result['error'],
                    'temp_id': temp_id
                }))
            
        elif message_type == 'file_message':
            file_data = data.get('file_data')
            filename = data.get('filename')
            message_text = data.get('message', '').strip()
            temp_id = data.get('temp_id')
            
            if file_data and filename:
                result = await self.save_file_message_atomic(file_data, filename, message_text)
                
                if result['success']:
                    saved_message = result['message']
                    attachments_data = await self.get_attachments_data(saved_message.id)
                    unread_counts = await self.get_unread_counts_for_participants()
                    
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message',
                            'message': message_text or '[File]',
                            'sender_id': self.user.id,
                            'sender_name': self.user.get_full_name() or self.user.username,
                            'timestamp': saved_message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            'message_id': saved_message.id,
                            'temp_id': temp_id,
                            'unread_counts': unread_counts,
                            'is_read': saved_message.is_read,
                            'read_by': [],
                            'attachments': attachments_data
                        }
                    )
                    
                    await self.broadcast_global_sidebar_update(saved_message, message_text or '[File]', unread_counts)
                else:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': result['error'],
                        'temp_id': temp_id
                    }))

        elif message_type == 'load_more':
            before_id = data.get('before_id')
            if before_id:
                messages = await self.get_previous_messages(before_id=before_id)
                await self.send(text_data=json.dumps({
                    'type': 'previous_messages',
                    'messages': messages,
                    'is_pagination': True
                }))
            
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
            message_ids = data.get('message_ids', [])
            if not message_ids:
                message_ids = await self.get_unread_message_ids_for_user()
            
            if message_ids:
                await self.mark_messages_read(message_ids)
                await self.handle_read_receipt_broadcast(message_ids)

    async def chat_message(self, event):
        response = {
            'type': 'chat_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp': event['timestamp'],
            'message_id': event.get('message_id'),
            'unread_counts': event.get('unread_counts', {}),
            'is_read': event.get('is_read', False),
            'read_by': event.get('read_by', []),
            'attachments': event.get('attachments', [])
        }
        if 'temp_id' in event:
            response['temp_id'] = event['temp_id']
        await self.send(text_data=json.dumps(response))
    
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
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'online_status',
                'user_id': event['user_id'],
                'is_online': event['is_online']
            }))

    async def broadcast_global_sidebar_update(self, message, content, unread_counts):
        """Notify all participants' global groups about the new message"""
        participants = await self.get_room_participants()
        for p_id in participants:
            await self.channel_layer.group_send(
                f"user_chat_{p_id}",
                {
                    'type': 'sidebar_update',
                    'room_id': self.room_id,
                    'last_message': content,
                    'last_message_sender': self.user.get_full_name() or self.user.username,
                    'last_activity': message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    'unread_count': unread_counts.get(str(p_id), unread_counts.get(p_id, 0)),
                    'total_unread_count': await self.get_total_unread_count_for_user(p_id)
                }
            )

    @database_sync_to_async
    def get_total_unread_count_for_user(self, user_id):
        try:
            from django.contrib.auth import get_user_model
            from .models import Message
            User = get_user_model()
            user = User.objects.get(id=user_id)
            return Message.objects.filter(
                room__participants=user
            ).exclude(sender=user).exclude(read_by=user).distinct().count()
        except Exception: return 0

    @database_sync_to_async
    def get_room_participants(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return list(room.participants.values_list('id', flat=True))
        except Exception: 
            return []

    @database_sync_to_async
    def is_room_participant(self):
        return ChatRoom.objects.filter(
            id=self.room_id, 
            participants=self.user
        ).exists()

    @database_sync_to_async
    def save_message_atomic(self, content):
        try:
            with transaction.atomic():
                room = ChatRoom.objects.select_for_update().get(id=self.room_id)
                
                if not room.participants.filter(id=self.user.id).exists():
                    return {'success': False, 'error': 'Not a member of this room'}
                
                msg = Message.objects.create(
                    room=room,
                    sender=self.user,
                    content=content
                )
                
               
                room.last_activity = timezone.now()
                room.save()
                
                return {'success': True, 'message': msg}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def save_file_message_atomic(self, file_data, filename, message_text):
        try:
            with transaction.atomic():
                room = ChatRoom.objects.select_for_update().get(id=self.room_id)
                
                if not room.participants.filter(id=self.user.id).exists():
                    return {'success': False, 'error': 'Not a member of this room'}
                
                format, imgstr = file_data.split(';base64,') if ';base64,' in file_data else (None, file_data)
                file_content = base64.b64decode(imgstr)
                
                msg = Message.objects.create(
                    room=room,
                    sender=self.user,
                    content=message_text or ''
                )
                
                mime_type = format.replace('data:', '') if format else ''
                file_type = self.determine_file_type(filename, mime_type)
                
                attachment = MessageAttachment.objects.create(
                    message=msg,
                    filename=filename,
                    file_size=len(file_content),
                    file_type=file_type,
                    mime_type=mime_type
                )
                attachment.file.save(filename, ContentFile(file_content))
                
                if file_type == 'image':
                    try:
                        img = Image.open(BytesIO(file_content))
                        img.thumbnail((200, 200))
                        thumb_io = BytesIO()
                        img.save(thumb_io, format='JPEG' if img.mode == 'RGB' else 'PNG')
                        attachment.thumbnail.save(f'thumb_{filename}', ContentFile(thumb_io.getvalue()))
                    except Exception: pass
                
                attachment.save()
                
                room.last_activity = timezone.now()
                room.save()
                
                return {'success': True, 'message': msg}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def determine_file_type(self, filename, mime_type):
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg']: return 'image'
        if ext in ['pdf']: return 'pdf'
        if ext in ['doc', 'docx', 'txt', 'rtf', 'odt']: return 'document'
        if ext in ['xls', 'xlsx', 'csv', 'ods']: return 'spreadsheet'
        if ext in ['zip', 'rar', '7z', 'tar', 'gz']: return 'archive'
        if ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm']: return 'video'
        if ext in ['mp3', 'wav', 'ogg', 'm4a', 'flac']: return 'audio'
        return 'other'

    @database_sync_to_async
    def get_attachments_data(self, message_id):
        attachments = MessageAttachment.objects.filter(message_id=message_id)
        return [{
            'id': att.id,
            'filename': att.filename,
            'file_size': att.file_size,
            'formatted_size': att.formatted_size,
            'file_type': att.file_type,
            'file_icon': att.file_icon,
            'file_url': att.file.url,
            'thumbnail_url': att.thumbnail.url if att.thumbnail else None,
            'mime_type': att.mime_type
        } for att in attachments]

    async def send_previous_messages(self, before_id=None):
        messages = await self.get_previous_messages(before_id=before_id)
        if not before_id:
           
            for msg in reversed(messages): 
                await self.send(text_data=json.dumps({
                    'type': 'chat_message',
                    'message': msg['content'],
                    'sender_id': msg['sender_id'],
                    'sender_name': msg['sender_name'],
                    'timestamp': msg['timestamp'],
                    'message_id': msg['message_id'],
                    'is_read': msg['is_read'],
                    'read_by': msg['read_by'],
                    'attachments': msg['attachments']
                }))
        else:
            
            pass

    @database_sync_to_async
    def get_previous_messages(self, before_id=None):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            qs = room.messages.select_related('sender').prefetch_related('read_by', 'attachments')
            
            if before_id:
                qs = qs.filter(id__lt=before_id).order_by('-id')[:50]
            else:
                qs = qs.order_by('-id')[:50]
            
            messages = list(qs)
            
            result = []
            for msg in messages:
                attachments = [{
                    'id': att.id,
                    'filename': att.filename,
                    'file_size': att.file_size,
                    'formatted_size': att.formatted_size,
                    'file_type': att.file_type,
                    'file_icon': att.file_icon,
                    'file_url': att.file.url,
                    'thumbnail_url': att.thumbnail.url if att.thumbnail else None,
                    'mime_type': att.mime_type
                } for att in msg.attachments.all()]
                
                result.append({
                    'content': msg.content,
                    'sender_id': msg.sender.id,
                    'sender_name': msg.sender.get_full_name() or msg.sender.username,
                    'timestamp': msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    'message_id': msg.id,
                    'is_read': msg.is_read,
                    'read_by': [u.id for u in msg.read_by.all()],
                    'attachments': attachments
                })
            return result
        except ChatRoom.DoesNotExist:
            return []

    @database_sync_to_async
    def get_unread_message_ids_for_user(self):
        try:
          
            from .models import ChatRoom, Message
            room = ChatRoom.objects.get(id=self.room_id)
            unread = Message.objects.filter(room=room).exclude(sender=self.user).exclude(read_by=self.user)
            return list(unread.values_list('id', flat=True))
        except Exception: return []

    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        try:
            with transaction.atomic():
                room = ChatRoom.objects.select_for_update().get(id=self.room_id)
                messages = Message.objects.select_for_update().filter(id__in=message_ids, room=room)
                for msg in messages:
                    msg.mark_as_read(self.user)
                
                return True
        except Exception: return False

    async def handle_read_receipt_broadcast(self, message_ids):
        """Helper to broadcast read receipts and update unread counts globally"""
        unread_counts = await self.get_unread_counts_for_participants()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'read_receipt',
                'user_id': self.user.id,
                'message_ids': message_ids
            }
        )

        participants = await self.get_room_participants()
        for p_id in participants:
            await self.channel_layer.group_send(
                f"user_chat_{p_id}",
                {
                    'type': 'sidebar_update',
                    'room_id': self.room_id,
                    'last_message': None, 
                    'last_activity': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'unread_count': unread_counts.get(str(p_id), unread_counts.get(p_id, 0)),
                    'total_unread_count': await self.get_total_unread_count_for_user(p_id)
                }
            )

    @database_sync_to_async
    def get_unread_counts_for_participants(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            counts = {}
            for participant in room.participants.all():
                count = room.get_unread_count(participant)
                if count > 0:
                    counts[str(participant.id)] = count
            return counts
        except Exception: return {}

class ChatListConsumer(AsyncWebsocketConsumer):
   
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return

        self.user_group_name = f"user_chat_{self.user.id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def sidebar_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'sidebar_update',
            'room_id': event['room_id'],
            'last_message': event['last_message'],
            'last_message_sender': event['last_message_sender'],
            'last_activity': event['last_activity'],
            'unread_count': event['unread_count'],
            'total_unread_count': event.get('total_unread_count', 0)
        }))