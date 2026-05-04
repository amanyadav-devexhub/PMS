from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from .models import Role, UserProfile

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(
            user=instance, 
            employee_id=f"EMP-{instance.id:04d}"
        )


