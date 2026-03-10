from notifications.models import Notification


def notification_count(request):
    """
    Returns unread notifications count for the current user.
    This dictionary is automatically available in all templates
    thanks to the context processor.
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': unread_count}
    return {'unread_notifications_count': 0}