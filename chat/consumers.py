# consumers.py - Update ChatConsumer class

import json
import base64
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from .models import ChatRoom, Message, MessageAttachment
from channels.layers import get_channel_layer
import os
from PIL import Image
from io import BytesIO

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    # Store connected users per room (simple in-memory - for production use Redis)
    room_online_users = {}

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
        
        # Send online status to room (directly, without HTTP call)
        await self.broadcast_online_status(True)

    async def disconnect(self, close_code):
        await self.broadcast_online_status(False)
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def broadcast_online_status(self, is_online):
        """Broadcast online status directly to the room group"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'online_status',
                'user_id': self.user.id,
                'is_online': is_online
            }
        )

    async def online_status(self, event):
        # Only send if the user is not self
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'online_status',
                'user_id': event['user_id'],
                'is_online': event['is_online']
            }))


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
                    'unread_counts': unread_counts,
                    'is_read': saved_message.is_read,
                    'read_by': [u.id for u in saved_message.read_by.all()],
                    'attachments': []
                }
            )
            
        elif message_type == 'file_message':
            # Handle file upload via WebSocket (base64 encoded)
            file_data = data.get('file_data')
            filename = data.get('filename')
            message_text = data.get('message', '').strip()
            
            if file_data and filename:
                saved_message = await self.save_file_message(file_data, filename, message_text)
                
                if saved_message:
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
                            'unread_counts': unread_counts,
                            'is_read': saved_message.is_read,
                            'read_by': [u.id for u in saved_message.read_by.all()],
                            'attachments': attachments_data
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
            message_ids = data.get('message_ids', [])
            if message_ids:
                await self.mark_messages_read(message_ids)
                # Broadcast read receipts to room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'read_receipt',
                        'user_id': self.user.id,
                        'message_ids': message_ids
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
            'unread_counts': event.get('unread_counts', {}),
            'is_read': event.get('is_read', False),
            'read_by': event.get('read_by', []),
            'attachments': event.get('attachments', [])
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
        # Only send if the user is not self
        if event['user_id'] != self.user.id:
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

    @database_sync_to_async
    def save_file_message(self, file_data, filename, message_text):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            
            # Decode base64 file data
            format, imgstr = file_data.split(';base64,') if ';base64,' in file_data else (None, file_data)
            file_content = base64.b64decode(imgstr)
            
            # Create message
            msg = Message.objects.create(
                room=room,
                sender=self.user,
                content=message_text or ''
            )
            
            # Determine file type and create thumbnail for images
            mime_type = format.replace('data:', '') if format else ''
            file_type = self.determine_file_type(filename, mime_type)
            
            # Save file
            from django.core.files.base import ContentFile
            attachment = MessageAttachment.objects.create(
                message=msg,
                filename=filename,
                file_size=len(file_content),
                file_type=file_type,
                mime_type=mime_type
            )
            
            # Save the file
            attachment.file.save(filename, ContentFile(file_content))
            
            # Create thumbnail for images
            if file_type == 'image':
                try:
                    from PIL import Image
                    from io import BytesIO
                    
                    img = Image.open(BytesIO(file_content))
                    img.thumbnail((200, 200))
                    thumb_io = BytesIO()
                    img.save(thumb_io, format='JPEG' if img.mode == 'RGB' else 'PNG')
                    attachment.thumbnail.save(f'thumb_{filename}', ContentFile(thumb_io.getvalue()))
                except Exception:
                    pass
            
            attachment.save()
            
            return msg
        except Exception as e:
            print(f"Error saving file: {e}")
            return None

    def determine_file_type(self, filename, mime_type):
        """Determine file type based on extension and MIME type"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        image_exts = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg']
        pdf_exts = ['pdf']
        doc_exts = ['doc', 'docx', 'txt', 'rtf', 'odt']
        spreadsheet_exts = ['xls', 'xlsx', 'csv', 'ods']
        archive_exts = ['zip', 'rar', '7z', 'tar', 'gz']
        video_exts = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm']
        audio_exts = ['mp3', 'wav', 'ogg', 'm4a', 'flac']
        
        if ext in image_exts:
            return 'image'
        elif ext in pdf_exts:
            return 'pdf'
        elif ext in doc_exts:
            return 'document'
        elif ext in spreadsheet_exts:
            return 'spreadsheet'
        elif ext in archive_exts:
            return 'archive'
        elif ext in video_exts:
            return 'video'
        elif ext in audio_exts:
            return 'audio'
        else:
            return 'other'

    @database_sync_to_async
    def get_attachments_data(self, message_id):
        """Get attachment data for a message"""
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
                'is_read': msg['is_read'],
                'read_by': msg['read_by'],
                'attachments': msg['attachments']
            }))

    @database_sync_to_async
    def get_previous_messages(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            messages = room.messages.select_related('sender').prefetch_related('read_by', 'attachments').all()[:50]
            
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
    def mark_messages_read(self, message_ids):
        messages = Message.objects.filter(
            id__in=message_ids,
            room_id=self.room_id
        ).exclude(sender=self.user)
        
        marked_count = 0
        for message in messages:
            if not message.read_by.filter(id=self.user.id).exists():
                message.mark_as_read(self.user)
                marked_count += 1
        
        return marked_count

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
        # Broadcast online status to room
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