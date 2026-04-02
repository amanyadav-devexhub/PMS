from django.db import models
from django.conf import settings
from django.utils import timezone

class ChatRoom(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)  # For group chats
    is_group = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='chat_rooms'
    )

    def __str__(self):
        return self.name or f"Room {self.id}"

    @property
    def last_message(self):
        return self.messages.order_by('-timestamp').first()

    def get_other_participant(self, user):
        """Get the other participant in a direct chat."""
        if not self.is_group:
            return self.participants.exclude(id=user.id).first()
        return None

    def get_display_name(self, user):
        """Get display name for the room relative to a user."""
        if self.is_group:
            return self.name or f"Group Chat {self.id}"
        other = self.get_other_participant(user)
        if other:
            return other.get_full_name() or other.username
        return f"Chat {self.id}"

    def get_other_initial(self, user):
        """Get first letter of the other participant's name."""
        if not self.is_group:
            other = self.get_other_participant(user)
            if other:
                name = other.get_full_name() or other.username
                return name[0].upper() if name else '?'
        return 'G'
    def get_unread_count(self, user):
        """Get number of unread messages for a user in this room"""
        return self.messages.filter(is_read=False).exclude(sender=user).count()


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

    class Meta:
        ordering = ['timestamp']
    
    def mark_as_read(self):
        """Mark message as read"""
        self.is_read = True
        self.save(update_fields=['is_read'])
    
    def __str__(self):
        return f"{self.sender} in {self.room}: {self.content[:50]}"