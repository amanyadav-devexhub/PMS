from django.urls import path
from . import views

# app_name = 'notifications'

urlpatterns = [
    # =========================================================================
    # NOTIFICATION VIEWS
    # =========================================================================
    
    path('all/', views.all_notifications, name='all_notifications'),
    # Purpose: Display all notifications for the logged-in user
    # Authentication: JWT or session required
    # Method: GET
    # Template: notifications/all_notifications.html
    # Features: Pagination, read/unread status filtering
    
    # =========================================================================
    # NOTIFICATION ACTIONS (Mark as Read)
    # =========================================================================
    
    path('mark-read/<int:notif_id>/', views.mark_as_read, name='mark_as_read'),
    # Purpose: Mark a single notification as read
    # Authentication: JWT or session required
    # Method: POST (AJAX) or GET
    # Returns: JSON response or redirect
    # Access: User can only mark their own notifications
    
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_as_read'),
    # Purpose: Mark all unread notifications as read for the current user
    # Authentication: JWT or session required
    # Method: POST (AJAX) or GET
    # Returns: JSON response or redirect
    # Feature: Bulk operation for better UX
]

# =========================================================================
# URL PATTERN SUMMARY
# =========================================================================
# Total URLs: 3
# 
# ┌─────────────────────────┬─────────────────────────────────────────────┐
# │ URL Pattern             │ Purpose                                     │
# ├─────────────────────────┼─────────────────────────────────────────────┤
# │ /notifications/all/     │ List all user notifications                 │
# │ /notifications/mark-read/<id>/ │ Mark single notification as read     │
# │ /notifications/mark-all-read/  │ Mark all notifications as read       │
# └─────────────────────────┴─────────────────────────────────────────────┘