from django.urls import path
from . import views



urlpatterns = [
    # =========================================================================
    # PAGE VIEWS (HTML Templates)
    # =========================================================================
    
    path('', views.chat_rooms, name='chat_rooms'),
    # Purpose: Display all chat rooms for the logged-in user
    # Authentication: JWT or session required
    # Method: GET
    # Template: chat/chat_rooms.html
    # Features: List of direct chats + group rooms
    
    path('room/<int:room_id>/', views.chat_room, name='chat_room'),
    # Purpose: Display a specific chat room with messages
    # Authentication: JWT or session required
    # Method: GET
    # Template: chat/chat_room.html
    # Features: Real-time messaging interface
    
    # =========================================================================
    # CHAT ROOM MANAGEMENT APIs
    # =========================================================================
    
    path('api/create-direct/<int:user_id>/', views.create_direct_room, name='create_direct_room'),
    # Purpose: Create or get existing direct chat room with another user
    # Authentication: JWT or session required
    # Method: POST
    # Returns: JSON with room_id and room details
    # Usage: When user clicks "Chat" on another user's profile
    
    path('api/create-group/', views.create_group_room, name='create_group_room'),
    # Purpose: Create a new group chat room
    # Authentication: JWT or session required
    # Method: POST
    # Expected data: name, participant_ids[]
    # Returns: JSON with created room details
    
    # =========================================================================
    # MESSAGING APIs
    # =========================================================================
    
    path('api/messages/<int:room_id>/', views.get_messages, name='get_messages'),
    # Purpose: Get paginated messages for a chat room
    # Authentication: JWT or session required
    # Method: GET
    # Query params: page, page_size
    # Returns: JSON with messages list and pagination info
    
    path('api/send/<int:room_id>/', views.send_message, name='send_message'),
    # Purpose: Send a new message to a chat room
    # Authentication: JWT or session required
    # Method: POST
    # Expected data: content (text), attachment (optional file)
    # Returns: JSON with created message details
    
    # =========================================================================
    # USER & ROOM LISTING APIs
    # =========================================================================
    
    path('api/search-users/', views.search_users, name='search_users'),
    # Purpose: Search for users by username/email for adding to chats
    # Authentication: JWT or session required
    # Method: GET
    # Query params: q (search query)
    # Returns: JSON with matching users list
    
    path('api/rooms/', views.get_user_rooms, name='get_user_rooms'),
    # Purpose: Get all chat rooms for the current user (for sidebar)
    # Authentication: JWT or session required
    # Method: GET
    # Returns: JSON with rooms list and last message preview
    
    path('api/users/', views.get_all_users, name='all_users'),
    # Purpose: Get list of all users (for starting new chats)
    # Authentication: JWT or session required
    # Method: GET
    # Returns: JSON with users list (excluding current user)
    
    path('api/projects/', views.list_projects, name='list_projects'),
    # Purpose: Get list of projects for group chat creation context
    # Authentication: JWT or session required
    # Method: GET
    # Returns: JSON with projects that user has access to
    
    # =========================================================================
    # NOTIFICATION & READ STATUS APIs
    # =========================================================================
    
    path('api/mark-read/<int:room_id>/', views.mark_messages_read, name='mark_messages_read'),
    # Purpose: Mark all messages in a room as read for current user
    # Authentication: JWT or session required
    # Method: POST
    # Returns: JSON with success status
    
    path('api/unread-count/', views.get_unread_counts, name='unread_counts'),
    # Purpose: Get unread message count per room (for notification badges)
    # Authentication: JWT or session required
    # Method: GET
    # Returns: JSON with room_id -> unread_count mapping
    
    # =========================================================================
    # FILE ATTACHMENT APIs
    # =========================================================================
    
    path('api/upload/<int:room_id>/', views.upload_file, name='upload_file'),
    # Purpose: Upload a file attachment to a chat room
    # Authentication: JWT or session required
    # Method: POST (multipart/form-data)
    # Expected: file field
    # Returns: JSON with attachment details
    
    path('api/download/<int:attachment_id>/', views.download_file, name='download_file'),
    # Purpose: Download an attached file from a message
    # Authentication: JWT or session required
    # Method: GET
    # Returns: File download response
]

# =========================================================================
# URL PATTERN SUMMARY
# =========================================================================
# Total URLs: 13
# 
# ┌─────────────────────────────┬─────────────────────────────────────────┐
# │ Category                    │ Endpoints                               │
# ├─────────────────────────────┼─────────────────────────────────────────┤
# │ Page Views                  │ 2 (/, /room/<id>)                       │
# │ Room Management             │ 2 (create-direct, create-group)         │
# │ Messaging                   │ 2 (messages, send)                      │
# │ User/Room Listing           │ 4 (search-users, rooms, users, projects)│
# │ Read Status                 │ 2 (mark-read, unread-count)             │
# │ File Attachments            │ 2 (upload, download)                    │
# └─────────────────────────────┴─────────────────────────────────────────┘