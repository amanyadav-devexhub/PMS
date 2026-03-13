from django.shortcuts import render,redirect,get_object_or_404

# Create your views here.
from django.shortcuts import render
from django.core.paginator import Paginator
from notifications.models import Notification


def all_notifications(request):
    # Get all notifications for the user
    notifications = request.user.notifications.all().order_by('-created_at')
    
    # Mark all as read when viewing the page (optional - remove if you want)
    # unread = notifications.filter(is_read=False)
    # unread.update(is_read=True)
    
    # Add pagination (optional)
    paginator = Paginator(notifications, 20)  # Show 20 notifications per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, "notifications/all_notifications.html", {
        "notifications": page_obj,
        "page_obj": page_obj
    })


def mark_as_read(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, user=request.user)
    notif.is_read = True
    notif.save()
    return redirect(request.META.get('HTTP_REFERER', '/'))  # go back to the page