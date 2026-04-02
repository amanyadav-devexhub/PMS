from django.db import models
from django.conf import settings
from django.utils import timezone

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

    def __str__(self):
        return self.name or f"Room {self.id}"

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
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    def get_participant_count(self):
        return self.participants.count()


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    content = models.TextField()
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
        return f"{self.sender} in {self.room}: {self.content[:50]}"

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