from notifications.models import Notification
from .permissions import (
    can_add_projects,
    can_add_task,
    can_change_task,
    can_delete_task,
    can_delete_projects,
    can_manage_departments,
    can_manage_designations,
    can_manage_projects,
    can_manage_roles,
    can_manage_users,
    can_view_all_projects,
    can_view_all_tasks,
    can_view_projects,
    can_view_task,
    can_view_user,
    dashboard_url_for,
    is_manager_like,
)

def notification_count(request):
    """
    Returns unread notifications count and recent notifications for the current user.
    """
    if request.user.is_authenticated:
        # Get unread count
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        
        # Get recent notifications (last 5, ordered by -created_at)
        recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        
        return {
            'unread_notifications_count': unread_count,
            'recent_notifications': recent_notifications
        }
    return {
        'unread_notifications_count': 0,
        'recent_notifications': []
    }


def permission_flags(request):
    user = getattr(request, 'user', None)

    if not user or not user.is_authenticated:
        return {
            'can_manage_users': False,
            'can_manage_roles': False,
            'can_manage_departments': False,
            'can_manage_designations': False,
            'can_add_projects': False,
            'can_delete_projects': False,
            'can_manage_projects': False,
            'can_view_projects': False,
            'can_view_all_projects': False,
            'can_add_task': False,
            'can_change_task': False,
            'can_delete_task': False,
            'can_view_task': False,
            'can_view_user': False,
            'can_view_all_tasks': False,
            'is_manager_like': False,
            'dashboard_url': '/dashboard/',
        }

    return {
        'can_manage_users': can_manage_users(user),
        'can_manage_roles': can_manage_roles(user),
        'can_manage_departments': can_manage_departments(user),
        'can_manage_designations': can_manage_designations(user),
        'can_add_projects': can_add_projects(user),
        'can_delete_projects': can_delete_projects(user),
        'can_manage_projects': can_manage_projects(user),
        'can_view_projects': can_view_projects(user),
        'can_view_all_projects': can_view_all_projects(user),
        'can_add_task': can_add_task(user),
        'can_change_task': can_change_task(user),
        'can_delete_task': can_delete_task(user),
        'can_view_task': can_view_task(user),
        'can_view_user': can_view_user(user),
        'can_view_all_tasks': can_view_all_tasks(user),
        'is_manager_like': is_manager_like(user),
        'dashboard_url': dashboard_url_for(user),
    }