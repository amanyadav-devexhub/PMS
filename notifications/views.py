from django.shortcuts import render,redirect,get_object_or_404

# Create your views here.
from django.shortcuts import render
from notifications.models import Notification


def all_notifications(request):
    # Get all notifications
    notifications = request.user.notifications.all().order_by('-created_at')

    # Mark all unread as read
    unread = notifications.filter(is_read=False)
    unread.update(is_read=True)

    return render(request, "notifications/all_notifications.html", {"notifications": notifications})


def mark_as_read(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, user=request.user)
    notif.is_read = True
    notif.save()
    return redirect(request.META.get('HTTP_REFERER', '/'))  # go back to the page