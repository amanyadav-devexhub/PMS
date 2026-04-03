# notifications/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()

class NotificationConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        self.user = self.scope["user"]
        
        # Reject unauthenticated users
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Create unique group for this user
        self.user_group_name = f"notifications_{self.user.id}"
        
        # Add user to their personal notification group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send unread count on connection
        await self.send_unread_count()
    
    async def disconnect(self, close_code):
        # Remove from notification group
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle messages from client"""
        data = json.loads(text_data)
        action = data.get('action')
        
        if action == 'mark_read':
            notification_id = data.get('notification_id')
            if notification_id:
                await self.mark_notification_read(notification_id)
                await self.send_unread_count()
        
        elif action == 'mark_all_read':
            await self.mark_all_notifications_read()
            await self.send_unread_count()
        
        elif action == 'get_unread_count':
            await self.send_unread_count()
        
        elif action == 'get_notifications':
            page = data.get('page', 1)
            page_size = data.get('page_size', 20)
            await self.send_notifications(page, page_size)
    
    async def notification_message(self, event):
        """Send notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': {
                'id': event['notification_id'],
                'message': event['message'],
                'created_at': event['created_at'],
                'is_read': False
            },
            'unread_count': event['unread_count']
        }))
    
    async def unread_count_update(self, event):
        """Send unread count update"""
        await self.send(text_data=json.dumps({
            'type': 'unread_count_update',
            'unread_count': event['unread_count']
        }))
    
    async def notification_read_update(self, event):
        """Notify when a notification is read"""
        await self.send(text_data=json.dumps({
            'type': 'notification_read',
            'notification_id': event['notification_id'],
            'unread_count': event['unread_count']
        }))
    
    async def send_unread_count(self):
        """Send current unread count to client"""
        count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'unread_count': count
        }))
    
    async def send_notifications(self, page, page_size):
        """Send paginated notifications to client"""
        notifications_data = await self.get_notifications(page, page_size)
        await self.send(text_data=json.dumps({
            'type': 'notifications_list',
            **notifications_data
        }))
    
    @database_sync_to_async
    def get_unread_count(self):
        return Notification.objects.filter(
            user=self.user, 
            is_read=False
        ).count()
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id, 
                user=self.user
            )
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
    
    @database_sync_to_async
    def mark_all_notifications_read(self):
        count = Notification.objects.filter(
            user=self.user, 
            is_read=False
        ).update(is_read=True)
        return count
    
    @database_sync_to_async
    def get_notifications(self, page, page_size):
        from django.core.paginator import Paginator
        
        notifications = Notification.objects.filter(
            user=self.user
        ).order_by('-created_at')
        
        paginator = Paginator(notifications, page_size)
        
        try:
            page_obj = paginator.page(page)
        except:
            page_obj = paginator.page(1)
        
        notifications_data = []
        for notif in page_obj:
            notifications_data.append({
                'id': notif.id,
                'message': notif.message,
                'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'is_read': notif.is_read
            })
        
        return {
            'notifications': notifications_data,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'unread_count': Notification.objects.filter(
                user=self.user, 
                is_read=False
            ).count()
        }