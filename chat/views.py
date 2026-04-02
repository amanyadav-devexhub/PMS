from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import ChatRoom
from users.decorators import jwt_or_session_required
from django.http import JsonResponse
from users.models import User

@jwt_or_session_required
def chat_rooms(request):
    rooms = request.user.chat_rooms.all()
    return render(request, 'chat/rooms.html', {'rooms': rooms})

@jwt_or_session_required
def chat_room(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    messages = room.messages.all()
    return render(request, 'chat/room.html', {
        'room': room,
        'messages': messages
    })

@jwt_or_session_required
def create_direct_room(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    if other_user == request.user:
        return JsonResponse({'error': 'Cannot chat with yourself'}, status=400)

    # Find or create direct chat room
    room = ChatRoom.objects.filter(
        is_group=False,
        participants=request.user
    ).filter(participants=other_user).first()

    if not room:
        room = ChatRoom.objects.create(is_group=False)
        room.participants.add(request.user, other_user)

    return JsonResponse({'room_id': room.id})