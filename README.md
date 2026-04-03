I see you want me to update the README with your GitHub repository URL and installation instructions. However, I cannot access the content of your GitHub repository at `https://github.com/amanyadav-devexhub/PMS.git` as it falls outside my supported retrieval scope.

**Here's the updated README with your repository URL and installation instructions:**

---

# PMS System - Project Management System

## Overview

A comprehensive Django-based Project Management System (PMS) with features for task tracking, project management, team collaboration, real-time chat, and notifications. The system supports multiple user roles (Admin, Team Lead, Employee) with granular permission controls.

**GitHub Repository:** [https://github.com/amanyadav-devexhub/PMS.git](https://github.com/amanyadav-devexhub/PMS.git)

## Features

### User Management
- Custom user model with role-based access control
- Department and designation management
- User profiles with employee details (salary, bank info, verification docs)
- Email-based account activation
- JWT authentication with session fallback

### Project Management
- Create, edit, delete projects
- Assign team members to projects
- Project resources (text, files, links)
- Project status tracking (Pending, Ongoing, Completed)

### Task Management
- Assign tasks to multiple employees
- Time tracking with start/pause/resume functionality
- Estimated time vs actual time spent
- Task deadlines and overdue notifications
- Task summary required before completion
- Task observers for additional visibility

### Real-time Chat
- Direct messaging between users
- Group chat rooms
- Real-time message delivery via WebSockets
- Typing indicators
- Read receipts
- Online status tracking

### Notifications
- In-app notifications for task assignments
- Real-time notifications via WebSockets
- Overdue task alerts
- Mark notifications as read/unread

### Analytics & Dashboard
- Role-based dashboards (Admin, Team Lead, Employee)
- User performance analytics
- Top performers tracking
- Task completion metrics

## Tech Stack

- **Backend**: Django 5.2, Django REST Framework
- **Authentication**: JWT (SimpleJWT) with cookie storage
- **Database**: SQLite (development), configurable for production
- **Real-time**: Django Channels, Redis channel layer
- **Frontend**: Django Templates, Tailwind CSS, HTMX/AJAX
- **Email**: SMTP (Gmail configured)

## Installation

### Prerequisites
- Python 3.8+
- Redis server (for WebSocket functionality)

### Setup Instructions

1. **Clone the repository**
```bash
git clone https://github.com/amanyadav-devexhub/PMS.git
cd PMS
```

2. **Create virtual environment**
```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run migrations**
```bash
python manage.py migrate
```

5. **Create superuser**
```bash
python manage.py createsuperuser
```

6. **Run Redis server** (required for WebSockets)
```bash
# macOS (with Homebrew)
brew install redis
redis-server

# Ubuntu/Debian
sudo apt install redis-server
redis-server

# Windows - Download from https://github.com/microsoftarchive/redis/releases
```

7. **Start development server**
```bash
python manage.py runserver
```

8. **Access the application**
- Open browser: http://127.0.0.1:8000
- Admin panel: http://127.0.0.1:8000/admin

## Configuration

### Email Settings (settings.py)
Email is configured for Gmail SMTP. Update settings.py:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "your-email@gmail.com"
EMAIL_HOST_PASSWORD = "your-app-password"
```

For development, use console backend:
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

### Redis Configuration
Update `CHANNEL_LAYERS` in settings.py if Redis runs on different host/port:
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

### Database Configuration
For production, update DATABASES in settings.py:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db_name',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## Project Structure

```
PMS/
├── manage.py
├── requirements.txt
├── pms_system/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py          # ASGI config for WebSockets
│   └── wsgi.py
├── users/               # User management, auth, roles
├── projects/            # Project CRUD and resources
├── Tasks/               # Task management with time tracking
├── chat/                # Real-time chat with WebSockets
├── notifications/       # Notification system
└── templates/           # Shared templates
```

## Authentication

The system uses **JWT authentication** with cookies:
- Login endpoint returns access/refresh tokens in HTTP-only cookies
- JWTAuthenticationMiddleware automatically authenticates requests
- Fallback to session authentication for backwards compatibility

**Login flow:**
1. POST to `/ajax_login/` with email/password
2. Server returns access_token and refresh_token as HTTP-only cookies
3. Subsequent requests automatically include tokens
4. Logout blacklists refresh token and clears cookies

## Role-Based Permissions

### Default Roles (auto-created on migrate)
- **ADMIN**: Full system access
- **TEAM_LEAD**: Add/change tasks, view projects, manage team
- **EMPLOYEE**: View and update assigned tasks

### Permission Checks
Use `@permission_required()` decorator:
```python
@permission_required('projects.add_projects')
def create_project(request):
    ...
```

## WebSocket Connections

### Chat WebSocket
```
ws://localhost:8000/ws/chat/<room_id>/
```

### Notifications WebSocket
```
ws://localhost:8000/ws/notifications/
```

## Running Tests
```bash
python manage.py test
```

## Troubleshooting

### Redis Connection Issues
- Ensure Redis server is running: `redis-cli ping`
- Check Redis host/port in settings.py

### Migration Issues
```bash
python manage.py makemigrations
python manage.py migrate --fake
python manage.py migrate
```

### Static Files
```bash
python manage.py collectstatic
```



**For issues or contributions, please visit:** [https://github.com/amanyadav-devexhub/PMS](https://github.com/amanyadav-devexhub/PMS)