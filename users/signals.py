from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from .models import Role, UserProfile

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_migrate)
def ensure_default_roles(sender, **kwargs):
    # Run once the users app migrations are complete.
    if sender.name != 'users':
        return

    app_labels = ['users', 'projects', 'Tasks', 'tasks', 'notifications']

    default_roles = {
        'ADMIN': None,
        'TEAM_LEAD': ['add_task', 'change_task', 'view_task', 'view_projects', 'change_projects'],
        'EMPLOYEE': ['view_task', 'change_task', 'view_projects'],
    }

    for role_name, codenames in default_roles.items():
        role, created = Role.objects.get_or_create(name=role_name)

        if codenames is None:
            perms = Permission.objects.filter(content_type__app_label__in=app_labels)
            if created or not role.permissions.exists():
                role.permissions.set(perms)
            continue

        if created or not role.permissions.exists():
            perms = Permission.objects.filter(
                content_type__app_label__in=app_labels,
                codename__in=codenames,
            )
            role.permissions.set(perms)

    User = get_user_model()
    for user in User.objects.filter(role_obj__isnull=True).exclude(role__isnull=True).exclude(role=''):
        role, _ = Role.objects.get_or_create(name=user.role)
        user.role_obj = role
        user.save(update_fields=['role_obj'])


        