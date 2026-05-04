from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import ChatRoom, Message
from users.decorators import jwt_or_session_required
from django.http import JsonResponse
from users.models import User
from .models import MessageAttachment, ChatRoom
from django.db.models import Q, Max
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django.http import HttpResponse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer



@jwt_or_session_required
def get_user_rooms(request):
    
    rooms = request.user.chat_rooms.all().order_by('-last_activity')
    
    rooms_data = []
    for room in rooms:
        last_msg = room.last_message
        rooms_data.append({
            'id': room.id,
            'name': room.get_display_name(request.user),
            'avatar_initial': room.get_avatar_initial(request.user),
            'is_group': room.is_group,
            'last_message_preview': last_msg.content[:50] if last_msg and last_msg.content else ('[File]' if last_msg else 'No messages'),
            'last_activity_short': room.last_activity.strftime("%H:%M") if room.last_activity.date() == timezone.now().date() else room.last_activity.strftime("%b %d"),
            'unread_count': room.get_unread_count(request.user),
            'participant_count': room.get_participant_count(),
        })
    
    return JsonResponse({'success': True, 'rooms': rooms_data})


@jwt_or_session_required
def chat_rooms(request):
    
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
            'participant_count': room.get_participant_count(),
            'last_activity': room.last_activity,
            'project_name': room.project_name
        })
    
    rooms_list.sort(key=lambda x: x['last_activity'] if x['last_activity'] else timezone.now() - timezone.timedelta(days=36500), reverse=True)
    
    
    has_dm_user_ids = set()
    for room in rooms:
        if not room.is_group:
            for p in room.participants.all():
                if p.id != request.user.id:
                    has_dm_user_ids.add(p.id)
                    
    
    users = User.objects.exclude(id=request.user.id).exclude(id__in=has_dm_user_ids)[:100]
    
    return render(request, 'chat/rooms.html', {
        'rooms': rooms_list,
        'users': users
    })


@jwt_or_session_required
def chat_room(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    
    
    unread_messages = Message.objects.filter(room=room).exclude(sender=request.user).exclude(read_by=request.user)
    message_ids = list(unread_messages.values_list('id', flat=True))
    
    if message_ids:
        for msg in unread_messages:
            msg.mark_as_read(request.user)
            
       
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{room_id}",
            {
                'type': 'read_receipt',
                'user_id': request.user.id,
                'message_ids': message_ids
            }
        )
       
        participants = list(room.participants.values_list('id', flat=True))
        for p_id in participants:
            async_to_sync(channel_layer.group_send)(
                f"user_chat_{p_id}",
                {
                    'type': 'sidebar_update',
                    'room_id': room.id,
                    'last_message': None,
                    'last_activity': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'unread_count': room.get_unread_count(User.objects.get(id=p_id)),
                    'total_unread_count': Message.objects.filter(room__participants__id=p_id).exclude(sender_id=p_id).exclude(read_by__id=p_id).distinct().count() or 0
                }
            )
    
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

   
    room = ChatRoom.objects.filter(is_group=False, participants=request.user) \
                           .filter(participants=other_user).first()

    if not room:
        from django.db import transaction
        with transaction.atomic():
            room = ChatRoom.objects.create(is_group=False)
            room.participants.add(request.user, other_user)
            room.last_activity = timezone.now()
            room.save()

    return JsonResponse({'room_id': room.id})


@csrf_exempt
@jwt_or_session_required
@require_http_methods(["POST"])
def create_group_room(request):
  
    try:
        data = json.loads(request.body)
        group_name = data.get('name', '').strip()
        participant_ids = data.get('participants', [])
        description = data.get('description', '')
        
        if not group_name:
            return JsonResponse({'error': 'Group name is required'}, status=400)
        
        if len(participant_ids) < 2:
            return JsonResponse({'error': 'Group needs at least 2 participants'}, status=400)
        
        from django.db import transaction
        with transaction.atomic():
      
            room = ChatRoom.objects.create(
                name=group_name,
                is_group=True,
                created_by=request.user,
                description=description,
                project_id=data.get('project_id')  
            )
            
     
            room.participants.add(request.user)
            for participant_id in participant_ids:
                try:
                    user = User.objects.get(id=participant_id)
                    room.participants.add(user)
                except User.DoesNotExist:
                    pass
            
            room.last_activity = timezone.now()
            room.save()
        
        return JsonResponse({'room_id': room.id, 'success': True})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)



@jwt_or_session_required
def get_messages(request, room_id):
    
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    
    after_id = request.GET.get('after', 0)
    before_id = request.GET.get('before', 0)
    limit = int(request.GET.get('limit', 50))
    
    qs = room.messages.select_related('sender').prefetch_related('read_by', 'attachments')
    
    if after_id and after_id != '0':
        messages = qs.filter(id__gt=after_id).order_by('id')[:limit]
    elif before_id and before_id != '0':
        messages = qs.filter(id__lt=before_id).order_by('-id')[:limit]
        messages = reversed(list(messages))
    else:
        messages = qs.order_by('-id')[:limit]
        messages = reversed(list(messages))
    
    messages_data = []
    for msg in messages:
       
        attachments_data = []
        for att in msg.attachments.all():
            attachments_data.append({
                'id': att.id,
                'filename': att.filename,
                'file_size': att.file_size,
                'formatted_size': att.formatted_size,
                'file_type': att.file_type,
                'file_icon': att.file_icon,
                'file_url': att.file.url,
                'thumbnail_url': att.thumbnail.url if att.thumbnail else None,
                'mime_type': att.mime_type
            })
        
        messages_data.append({
            'message_id': msg.id,
            'message': msg.content,
            'sender_id': msg.sender.id,
            'sender_name': msg.sender.get_full_name() or msg.sender.username,
            'timestamp': msg.timestamp.isoformat(),
            'is_read': msg.is_read,
            'read_by': [user.id for user in msg.read_by.all()],
            'attachments': attachments_data  
        })
    
    return JsonResponse({'messages': messages_data})



@csrf_exempt
@jwt_or_session_required
@require_http_methods(["POST"])
def send_message(request, room_id):
    
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    
    try:
        data = json.loads(request.body)
        content = data.get('message', '').strip()
        
        if not content or len(content) > 5000:
            return JsonResponse({'success': False, 'error': 'Invalid message'}, status=400)
        
        from django.db import transaction
        with transaction.atomic():
           
            room_locked = ChatRoom.objects.select_for_update().get(id=room_id)
            
          
            if not room_locked.participants.filter(id=request.user.id).exists():
                return JsonResponse({'success': False, 'error': 'Not a member'}, status=403)
                
            message = Message.objects.create(
                room=room_locked,
                sender=request.user,
                content=content
            )
            
            room_locked.last_activity = timezone.now()
            room_locked.save()
        
        message_data = {
            'message_id': message.id,
            'message': message.content,
            'sender_id': message.sender.id,
            'sender_name': message.sender.get_full_name() or message.sender.username,
            'timestamp': message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'is_read': message.is_read,
            'read_by': [u.id for u in message.read_by.all()],
            'attachments': []
        }
        
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{room_id}",
            {
                'type': 'chat_message',
                **message_data
            }
        )
        
        return JsonResponse({
            'success': True,
            'message_data': message_data
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)



@jwt_or_session_required
def search_users(request):
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
    
    users = users.filter(is_active=True)[:20]
    
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



@csrf_exempt
@jwt_or_session_required
@require_http_methods(["POST"])
def mark_messages_read(request, room_id):
    
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    
    messages = Message.objects.filter(room=room).exclude(sender=request.user).exclude(read_by=request.user)
    message_ids = list(messages.values_list('id', flat=True))
    
    updated = 0
    for msg in messages:
        msg.mark_as_read(request.user)
        updated += 1
    
    if updated > 0:
      
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{room_id}",
            {
                'type': 'read_receipt',
                'user_id': request.user.id,
                'message_ids': message_ids
            }
        )
        
        
        from .consumers import ChatConsumer
       
        participants = list(room.participants.values_list('id', flat=True))
        
        
        unread_counts = {}
        for p_id in participants:
            try:
                user = User.objects.get(id=p_id)
                unread_counts[str(p_id)] = room.get_unread_count(user)
            except: pass

        for p_id in participants:
            
            total_unread = Message.objects.filter(
                room__participants__id=p_id
            ).exclude(sender_id=p_id).exclude(read_by__id=p_id).distinct().count()
            
            async_to_sync(channel_layer.group_send)(
                f"user_chat_{p_id}",
                {
                    'type': 'sidebar_update',
                    'room_id': room.id,
                    'last_message': None,
                    'last_activity': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'unread_count': unread_counts.get(str(p_id), 0),
                    'total_unread_count': total_unread
                }
            )
    
    return JsonResponse({'success': True, 'marked_count': updated})



@jwt_or_session_required
def get_unread_counts(request):
    
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
    
    users = User.objects.exclude(id=request.user.id).filter(is_active=True)
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'full_name': user.get_full_name() or user.username,
            'avatar_initial': (user.get_full_name() or user.username)[0].upper(),
            'role': getattr(user, 'role', 'Member')
        })
    
    return JsonResponse({'users': users_data})



@csrf_exempt 
@jwt_or_session_required
@require_http_methods(["POST"])
def upload_file(request, room_id):
    
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    uploaded_file = request.FILES['file']
    message_text = request.POST.get('message', '').strip()
    
    if uploaded_file.size > 25 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Max 25MB'}, status=400)
    
    from django.db import transaction
    with transaction.atomic():
        room_locked = ChatRoom.objects.select_for_update().get(id=room_id)
        
        if not room_locked.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Not a member'}, status=403)

        message = Message.objects.create(
            room=room_locked,
            sender=request.user,
            content=message_text or ''
        )
        
        file_type = determine_file_type(uploaded_file.name, uploaded_file.content_type)
        
        attachment = MessageAttachment.objects.create(
            message=message,
            filename=uploaded_file.name,
            file_size=uploaded_file.size,
            file_type=file_type,
            mime_type=uploaded_file.content_type
        )
        
      
        attachment.file.save(uploaded_file.name, uploaded_file)
        
        if file_type == 'image':
            try:
                img = Image.open(uploaded_file)
                img.thumbnail((200, 200))
                thumb_io = BytesIO()
                img.save(thumb_io, format='JPEG' if img.mode == 'RGB' else 'PNG')
                attachment.thumbnail.save(f'thumb_{uploaded_file.name}', ContentFile(thumb_io.getvalue()))
            except Exception:
                pass
        
        attachment.save()
        
        room_locked.last_activity = timezone.now()
        room_locked.save()
    
    attachment_data = {
        'id': attachment.id,
        'filename': attachment.filename,
        'file_size': attachment.file_size,
        'formatted_size': attachment.formatted_size,
        'file_type': attachment.file_type,
        'file_icon': attachment.file_icon,
        'file_url': attachment.file.url,
        'thumbnail_url': attachment.thumbnail.url if attachment.thumbnail else None,
        'mime_type': attachment.mime_type
    }

  
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{room_id}",
        {
            'type': 'chat_message',
            'message_id': message.id,
            'message': message.content or '[File]',
            'sender_id': request.user.id,
            'sender_name': request.user.get_full_name() or request.user.username,
            'timestamp': message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'is_read': message.is_read,
            'read_by': [],
            'attachments': [attachment_data]
        }
    )
    
    return JsonResponse({
        'success': True,
        'message_id': message.id,
        'attachment': attachment_data
    })



@jwt_or_session_required
def download_file(request, attachment_id):
   
    attachment = get_object_or_404(MessageAttachment, id=attachment_id)
    
   
    room = attachment.message.room
    if request.user not in room.participants.all():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    response = HttpResponse(attachment.file.read(), content_type=attachment.mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
    return response



def determine_file_type(filename, mime_type):
    """Determine file type based on extension and MIME type"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    image_exts = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg']
    pdf_exts = ['pdf']
    doc_exts = ['doc', 'docx', 'txt', 'rtf', 'odt']
    spreadsheet_exts = ['xls', 'xlsx', 'csv', 'ods']
    archive_exts = ['zip', 'rar', '7z', 'tar', 'gz']
    video_exts = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm']
    audio_exts = ['mp3', 'wav', 'ogg', 'm4a', 'flac']
    
    if ext in image_exts:
        return 'image'
    elif ext in pdf_exts:
        return 'pdf'
    elif ext in doc_exts:
        return 'document'
    elif ext in spreadsheet_exts:
        return 'spreadsheet'
    elif ext in archive_exts:
        return 'archive'
    elif ext in video_exts:
        return 'video'
    elif ext in audio_exts:
        return 'audio'
    else:
        return 'other'



@jwt_or_session_required
def list_projects(request):
    
    from projects.models import Projects
    
    if request.user.is_superuser:
        projects = Projects.objects.all()
    else:
        projects = Projects.objects.filter(Q(assigned_to=request.user) | Q(created_by=request.user)).distinct()
        
    projects_data = []
    for p in projects:
        projects_data.append({
            'id': p.id,
            'name': p.name
        })
        
    return JsonResponse({'projects': projects_data})
