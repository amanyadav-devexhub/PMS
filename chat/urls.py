from django.urls import path
from . import views

urlpatterns = [
    path('rooms/', views.chat_rooms, name='chat_rooms'),
    path('room/<int:room_id>/', views.chat_room, name='chat_room'),
    # API for creating direct message room
    path('api/create-direct/<int:user_id>/', views.create_direct_room, name='create_direct_room'),
]