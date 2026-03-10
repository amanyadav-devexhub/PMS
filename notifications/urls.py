from django.urls import path
from . import views

urlpatterns = [
    path('all/', views.all_notifications, name='all_notifications'),
    path('mark-read/<int:notif_id>/', views.mark_as_read, name='mark_as_read'),
]