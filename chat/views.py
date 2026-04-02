from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import ChatRoom, Message
from users.decorators import jwt_or_session_required
from django.http import JsonResponse
from users.models import User
from django.db.models import Q, Max
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json

@jwt_or_session_required
def chat_rooms(request):
    """Display all chat rooms for the user with recent messages"""
    rooms = request.user.chat_rooms.all()
    
    rooms_list = []
    for room in rooms:
        last_msg = room.last_message
        rooms_list.append({
            'id': room.id,
            'display_name': room.get_display_name(request.user),
            'avatar_initial': room.get_avatar_initial(request.user),
            'is_group': room.is_group,
            'last_message': last_msg.content if last_msg else None,
            'last_message_time': last_msg.timestamp if last_msg else None,
            'last_message_sender': last_msg.sender.get_full_name() or last_msg.sender.username if last_msg else None,
            'unread_count': room.get_unread_count(request.user),
            'participant_count': room.get_participant_count()
        })
    
    # Sort by last message time (most recent first), putting None at the end
    rooms_list.sort(key=lambda x: x['last_message_time'] or timezone.now(), reverse=True)
    
    # Alternative: sort None values to the end
    # rooms_list.sort(key=lambda x: (x['last_message_time'] is None, x['last_message_time']), reverse=True)
    
    # Get all users for new chat (excluding current user)
    users = User.objects.exclude(id=request.user.id).exclude(is_superuser=True)[:100]
    
    return render(request, 'chat/rooms.html', {
        'rooms': rooms_list,
        'users': users
    })

@jwt_or_session_required
def chat_room(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    
    # Mark all messages as read when entering room
    unread_messages = Message.objects.filter(room=room, is_read=False).exclude(sender=request.user)
    for msg in unread_messages:
        msg.mark_as_read(request.user)
    
    return render(request, 'chat/room.html', {
        'room': room,
        'display_name': room.get_display_name(request.user),
        'avatar_initial': room.get_avatar_initial(request.user),
        'is_group': room.is_group,
        'participants': room.participants.exclude(id=request.user.id) if not room.is_group else room.participants.all()
    })

@jwt_or_session_required
def create_direct_room(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    if other_user == request.user:
        return JsonResponse({'error': 'Cannot chat with yourself'}, status=400)

    # Find or create direct chat room
    rooms_for_user = request.user.chat_rooms.filter(is_group=False)
    room = None
    
    for r in rooms_for_user:
        if other_user in r.participants.all():
            room = r
            break

    if not room:
        room = ChatRoom.objects.create(is_group=False)
        room.participants.add(request.user, other_user)

    return JsonResponse({'room_id': room.id})

@jwt_or_session_required
@require_http_methods(["POST"])
def create_group_room(request):
    """Create a new group chat"""
    try:
        data = json.loads(request.body)
        group_name = data.get('name', '').strip()
        participant_ids = data.get('participants', [])
        description = data.get('description', '')
        
        if not group_name:
            return JsonResponse({'error': 'Group name is required'}, status=400)
        
        if len(participant_ids) < 2:
            return JsonResponse({'error': 'Group needs at least 2 participants'}, status=400)
        
        # Create group room
        room = ChatRoom.objects.create(
            name=group_name,
            is_group=True,
            created_by=request.user,
            description=description
        )
        
        # Add participants
        room.participants.add(request.user)
        for participant_id in participant_ids:
            try:
                user = User.objects.get(id=participant_id)
                room.participants.add(user)
            except User.DoesNotExist:
                pass
        
        return JsonResponse({'room_id': room.id, 'success': True})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

@jwt_or_session_required
def get_messages(request, room_id):
    """Get messages for a room with pagination"""
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    
    after_id = request.GET.get('after', 0)
    limit = int(request.GET.get('limit', 50))
    
    if after_id and after_id != '0':
        messages = room.messages.filter(id__gt=after_id).select_related('sender')[:limit]
    else:
        messages = room.messages.all().select_related('sender')[:limit]
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'message_id': msg.id,
            'message': msg.content,
            'sender_id': msg.sender.id,
            'sender_name': msg.sender.get_full_name() or msg.sender.username,
            'timestamp': msg.timestamp.isoformat(),
            'is_read': msg.is_read,
            'read_by': [user.id for user in msg.read_by.all()]
        })
    
    return JsonResponse({'messages': messages_data})

@csrf_exempt
@jwt_or_session_required
@require_http_methods(["POST"])
def send_message(request, room_id):
    """Send message via HTTP fallback"""
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    
    try:
        data = json.loads(request.body)
        content = data.get('message', '').strip()
        
        if not content or len(content) > 5000:
            return JsonResponse({'success': False, 'error': 'Invalid message'}, status=400)
        
        message = Message.objects.create(
            room=room,
            sender=request.user,
            content=content
        )
        
        message_data = {
            'message_id': message.id,
            'message': message.content,
            'sender_id': message.sender.id,
            'sender_name': message.sender.get_full_name() or message.sender.username,
            'timestamp': message.timestamp.isoformat(),
            'is_read': message.is_read
        }
        
        return JsonResponse({
            'success': True,
            'message_data': message_data
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

@jwt_or_session_required
def search_users(request):
    """Search for users to add to chat or start conversation"""
    query = request.GET.get('q', '').strip()
    exclude_ids = request.GET.get('exclude', '')
    exclude_list = [int(id) for id in exclude_ids.split(',') if id]
    
    if len(query) < 2:
        return JsonResponse({'users': []})
    
    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query)
    ).exclude(id=request.user.id)
    
    if exclude_list:
        users = users.exclude(id__in=exclude_list)
    
    users = users.exclude(is_superuser=True)[:20]
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'email': user.email,
            'role': getattr(user, 'role', 'Member'),
            'avatar_initial': (user.get_full_name() or user.username)[0].upper()
        })
    
    return JsonResponse({'users': users_data})

@jwt_or_session_required
@require_http_methods(["POST"])
def mark_messages_read(request, room_id):
    """Mark messages as read"""
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    
    messages = Message.objects.filter(room=room, is_read=False).exclude(sender=request.user)
    updated = 0
    for msg in messages:
        msg.mark_as_read(request.user)
        updated += 1
    
    return JsonResponse({'success': True, 'marked_count': updated})

@jwt_or_session_required
def get_unread_counts(request):
    """Get unread message counts for all rooms"""
    rooms = request.user.chat_rooms.all()
    
    unread_counts = {}
    for room in rooms:
        count = room.get_unread_count(request.user)
        if count > 0:
            unread_counts[room.id] = count
    
    total_unread = sum(unread_counts.values())
    
    return JsonResponse({
        'success': True,
        'unread_counts': unread_counts,
        'total_unread': total_unread
    })

@jwt_or_session_required
def get_all_users(request):
    """Get all users for group creation"""
    users = User.objects.exclude(id=request.user.id).exclude(is_superuser=True)
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'full_name': user.get_full_name() or user.username,
            'avatar_initial': (user.get_full_name() or user.username)[0].upper(),
            'role': getattr(user, 'role', 'Member')
        })
    
    return JsonResponse({'users': users_data})