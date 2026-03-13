from notifications.models import Notification


from notifications.models import Notification

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