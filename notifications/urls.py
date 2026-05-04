from django.urls import path
from . import views

# app_name = 'notifications'

urlpatterns = [
    # =========================================================================
    # NOTIFICATION VIEWS
    # =========================================================================
    
    path('all/', views.all_notifications, name='all_notifications'),
    # =========================================================================
    # NOTIFICATION ACTIONS (Mark as Read)
    # =========================================================================
    
    path('mark-read/<int:notif_id>/', views.mark_as_read, name='mark_as_read'),
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_as_read'),

]
