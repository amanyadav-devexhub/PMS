# urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_rooms, name='chat_rooms'),
    path('room/<int:room_id>/', views.chat_room, name='chat_room'),
    # API endpoints
    path('api/create-direct/<int:user_id>/', views.create_direct_room, name='create_direct_room'),
    path('api/create-group/', views.create_group_room, name='create_group_room'),
    path('api/messages/<int:room_id>/', views.get_messages, name='get_messages'),
    path('api/send/<int:room_id>/', views.send_message, name='send_message'),
    path('api/search-users/', views.search_users, name='search_users'),
    path('api/mark-read/<int:room_id>/', views.mark_messages_read, name='mark_messages_read'),
    path('api/unread-count/', views.get_unread_counts, name='unread_counts'),
    path('api/users/', views.get_all_users, name='all_users'),
    # File upload endpoints
    path('api/upload/<int:room_id>/', views.upload_file, name='upload_file'),
    path('api/download/<int:attachment_id>/', views.download_file, name='download_file'),
]
