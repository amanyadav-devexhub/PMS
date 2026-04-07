# models.py - Add these new models and update Message model

from django.db import models
from django.conf import settings
from django.utils import timezone
import os

class ChatRoom(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    is_group = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_rooms'
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='chat_rooms'
    )
    group_avatar = models.ImageField(upload_to='group_avatars/', blank=True, null=True)
    description = models.TextField(blank=True, max_length=500)
    project = models.ForeignKey(
        'projects.Projects',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_rooms'
    )
    last_activity = models.DateTimeField(default=timezone.now)

    @property
    def project_name(self):
        return self.project.name if self.project else None

    def __str__(self):
        return self.name if self.is_group else f"DM: {list(self.participants.all())}"

    @property
    def last_message(self):
        return self.messages.order_by('-timestamp').first()

    def get_other_participants(self, user):
        """Get all other participants except the given user"""
        return self.participants.exclude(id=user.id)

    def get_other_participant(self, user):
        """For direct chats, get the other participant"""
        if not self.is_group:
            return self.participants.exclude(id=user.id).first()
        return None

    def get_display_name(self, user):
        if self.is_group:
            return self.name or f"Group Chat {self.id}"
        other = self.get_other_participant(user)
        if other:
            return other.get_full_name() or other.username
        return f"Chat {self.id}"

    def get_avatar_initial(self, user):
        if self.is_group:
            if self.name:
                return self.name[0].upper()
            return 'G'
        other = self.get_other_participant(user)
        if other:
            name = other.get_full_name() or other.username
            return name[0].upper() if name else '?'
        return '?'

    
    def get_unread_count(self, user):
        return self.messages.exclude(sender=user).exclude(read_by=user).count()

    def get_participant_count(self):
        return self.participants.count()


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    content = models.TextField(blank=True)  # Allow empty content for file-only messages
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='read_messages'
    )

    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.sender} in {self.room}: {self.content[:50] if self.content else '[File]'}"

    def mark_as_read(self, user):
        """Mark message as read by a specific user"""
        if user != self.sender and not self.read_by.filter(id=user.id).exists():
            self.read_by.add(user)
            # If all participants except sender have read it, mark as read
            room_participants = self.room.participants.exclude(id=self.sender.id)
            if room_participants.count() > 0 and all(
                self.read_by.filter(id=p.id).exists() for p in room_participants
            ):
                self.is_read = True
                self.save()


class MessageAttachment(models.Model):
    """Model for file attachments in messages"""
    FILE_TYPE_CHOICES = [
        ('image', 'Image'),
        ('pdf', 'PDF Document'),
        ('document', 'Document'),
        ('spreadsheet', 'Spreadsheet'),
        ('archive', 'Archive'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('other', 'Other'),
    ]
    
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')
    mime_type = models.CharField(max_length=100, blank=True)
    thumbnail = models.ImageField(upload_to='chat_thumbnails/%Y/%m/%d/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment for message {self.message.id}: {self.filename}"
    
    @property
    def formatted_size(self):
        """Return human-readable file size"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.1f} GB"
    
    @property
    def file_icon(self):
        """Return appropriate icon for file type"""
        icons = {
            'image': '🖼️',
            'pdf': '📄',
            'document': '📝',
            'spreadsheet': '📊',
            'archive': '📦',
            'video': '🎥',
            'audio': '🎵',
            'other': '📎'
        }
        return icons.get(self.file_type, '📎')
    
    @property
    def file_extension(self):
        """Get file extension"""
        return os.path.splitext(self.filename)[1].lower()