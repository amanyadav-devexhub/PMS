from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from notifications.models import Notification
from users.decorators import jwt_or_session_required
from django.utils import timezone


@jwt_or_session_required
def all_notifications(request):

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        
        notifications = request.user.notifications.all().order_by('-created_at')
        
        page = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 20)
        
        paginator = Paginator(notifications, page_size)
        try:
            notifications_page = paginator.page(page)
        except:
            notifications_page = paginator.page(1)
        
        notifications_data = []
        for notif in notifications_page:
            local_time = timezone.localtime(notif.created_at)
            notifications_data.append({
                'id': notif.id,
                'message': notif.message,
                'created_at': local_time.strftime('%Y-%m-%d %H:%M:%S'),
                'is_read': notif.is_read,
                'target_url': notif.target_url
            })
        
        return JsonResponse({
            'success': True,
            'notifications': notifications_data,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': notifications_page.number,
            'has_previous': notifications_page.has_previous(),
            'has_next': notifications_page.has_next(),
            'unread_count': request.user.notifications.filter(is_read=False).count()
        })
    
    notifications = request.user.notifications.all().order_by('-created_at')
    
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, "notifications/all_notifications.html", {
        "notifications": page_obj,
        "page_obj": page_obj
    })


@jwt_or_session_required
@csrf_exempt
def mark_as_read(request, notif_id):

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    notif = get_object_or_404(Notification, id=notif_id, user=request.user)
    notif.is_read = True
    notif.save()
    
    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read',
            'notification_id': notif_id
        })
    
    return redirect(request.META.get('HTTP_REFERER', '/'))


@jwt_or_session_required
@csrf_exempt
def mark_all_as_read(request):
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    unread_count = request.user.notifications.filter(is_read=False).count()
    request.user.notifications.filter(is_read=False).update(is_read=True)
    
    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': f'All {unread_count} notifications marked as read',
            'marked_count': unread_count
        })
    
    return redirect(request.META.get('HTTP_REFERER', '/'))

