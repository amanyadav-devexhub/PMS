from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from .models import Role, UserProfile

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Generate a default employee ID based on user ID to satisfy UNIQUE constraint
        UserProfile.objects.create(
            user=instance, 
            employee_id=f"EMP-{instance.id:04d}"
        )



# @receiver(post_migrate)
# def ensure_default_roles(sender, **kwargs):
#     # Run once the users app migrations are complete
#     if sender.name != 'users':
#         return

#     # Permission mapping - exact names as they exist in database
#     permission_map = {
#         # Task permissions (Tasks app - note capital T)
#         'add_task': ('Tasks', 'add_task'),
#         'change_task': ('Tasks', 'change_task'),
#         'view_task': ('Tasks', 'view_task'),
#         'delete_task': ('Tasks', 'delete_task'),
        
#         # Project permissions (projects app - lowercase)
#         'view_projects': ('projects', 'view_projects'),
#         'add_projects': ('projects', 'add_projects'),
#         'change_projects': ('projects', 'change_projects'),
#         'delete_projects': ('projects', 'delete_projects'),
        
#         # User permissions
#         'view_user': ('users', 'view_user'),
#         'add_user': ('users', 'add_user'),
#         'change_user': ('users', 'change_user'),
#         'delete_user': ('users', 'delete_user'),
#     }
    
#     default_roles = {
#         'ADMIN': None,  # Gets ALL permissions
#         'TEAM_LEAD': [
#             'add_task', 'change_task', 'view_task',
#             'view_projects', 'change_projects',
#             'view_user',
#         ],
#         'EMPLOYEE': [
#             'view_task', 'change_task',  # Employees can update their own tasks (start/pause/complete)
#             'view_projects',
#         ],
#     }

#     for role_name, codenames in default_roles.items():
#         role, created = Role.objects.get_or_create(name=role_name)
        
#         if codenames is None:
#             # ADMIN gets all permissions from relevant apps
#             perms = Permission.objects.filter(
#                 content_type__app_label__in=['users', 'projects', 'Tasks', 'notifications']
#             )
#             if created or not role.permissions.exists():
#                 role.permissions.set(perms)
#                 print(f"✅ Role '{role_name}' created with {perms.count()} permissions")
#             continue
        
#         # For other roles, get specific permissions
#         if created or not role.permissions.exists():
#             perms_to_add = []
#             missing_perms = []
            
#             for codename in codenames:
#                 if codename in permission_map:
#                     app_label, perm_codename = permission_map[codename]
#                     try:
#                         perm = Permission.objects.get(
#                             content_type__app_label=app_label,
#                             codename=perm_codename
#                         )
#                         perms_to_add.append(perm)
#                     except Permission.DoesNotExist:
#                         missing_perms.append(f"{app_label}.{perm_codename}")
#                         print(f"⚠️ Permission not found: {app_label}.{perm_codename}")
#                 else:
#                     missing_perms.append(codename)
            
#             role.permissions.set(perms_to_add)
#             print(f"✅ Role '{role_name}' created with {len(perms_to_add)} permissions")
#             if missing_perms:
#                 print(f"   Missing: {', '.join(missing_perms)}")