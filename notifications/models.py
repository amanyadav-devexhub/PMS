from django.db import models
from users.models import User
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

# Create your models here.

class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="notifications")
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    link = models.URLField(max_length=500, null=True, blank=True)

    @property
    def target_url(self):
        if self.link:
            return self.link
        
        if self.content_object:
            try:
                model_name = self.content_type.model.lower()
                if model_name == 'task':
                    return f"{reverse('employee_tasks')}?task_id={self.object_id}"
                elif model_name in ['projects', 'project']:
                    return reverse('view_project_detail', args=[self.object_id])
            except Exception:
                pass
        return None

    def __str__(self):
        return f"Notification for {self.user.username}"
