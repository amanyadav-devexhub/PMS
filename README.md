# 📋 Project Management System (PMS)

<div align="center">

![Django](https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.0-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.14+-3776AB?style=for-the-badge&logo=python&logoColor=white)

**A powerful, role-based Project Management System for teams of all sizes**

[Features](#features) • [Tech Stack](#tech-stack) • [Installation](#installation) • [Usage](#usage) • [Screenshots](#screenshots)

</div>

---

## ✨ Features

### 👥 User Roles & Permissions

| Role | Capabilities |
|------|--------------|
| **👑 Admin** | Full system control - manage members, projects, departments, and designations |
| **👔 Team Lead** | Task assignment, progress tracking, team management |
| **👩‍💻 Employee** | View tasks, update status, receive notifications |

### 📌 Task Management
- ✅ Create, assign, and track tasks with deadlines
- ⏱️ Built-in timer for task tracking
- 📊 Task statuses: `PENDING` → `ONGOING` → `COMPLETED`
- 📅 Start and end date tracking

### 🔔 Real-time Notifications
- 🔴 Unread notification badge
- 📬 Dropdown panel with latest 5 notifications
- 📄 Dedicated "All Notifications" page
- ✨ Mark notifications as read
- 🎯 Automatic triggers:
  - Task assignment → Employee notified
  - Task started → Admin & Team Lead notified
  - Task completed → Admin & Team Lead notified

### 📊 Role-based Dashboards
- Personalized views based on user role
- Quick access to relevant tasks and projects
- Real-time progress tracking

### 🔐 Authentication & Security
- JWT-based authentication
- Role-based access control (RBAC)
- Secure API endpoints

---

## 🛠️ Tech Stack

**Backend**
- Django 6.0
- Django REST Framework
- JWT Authentication

**Frontend**
- Tailwind CSS 3.0
- HTML5
- JavaScript (ES6+)

**Database**
- SQLite (Development)
- PostgreSQL 15+ (Production)

**Requirements**
- Python 3.14+

---

## 🚀 Installation

### Prerequisites
- Python 3.14 or higher
- Git
- Virtual environment (recommended)

### Step-by-Step Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/pms_system.git
cd pms_system

2.Create virtual environment
# Windows
    python -m venv venv
    venv\Scripts\activate

    # Linux/Mac
    python -m venv venv
    source venv/bin/activate

3.Install dependencies
    pip install -r requirements.txt

4.Set up database
    python manage.py makemigrations
    python manage.py migrate

5.Create superuser (Admin)
    python manage.py createsuperuser

6.Run development server
    python manage.py runserver

7.Access the application
    http://127.0.0.1:8000/

8.Project Structure
    pms_system/
│
├── 📁 users/                 # User management & authentication
│   ├── models.py            # User, Role models
│   ├── views.py             # Login, registration views
│   └── utils.py             # Role-based permissions
│
├── 📁 projects/             # Projects & tasks management
│   ├── models.py            # Project, Task models
│   ├── views.py             # CRUD operations
│   └── forms.py             # Project/Task forms
│
├── 📁 notifications/        # Notification system
│   ├── models.py            # Notification model
│   ├── views.py             # Notification handlers
│   └── templates/           # Notification UI
│
├── 📁 templates/            # Global HTML templates
│   ├── base.html            # Base template
│   ├── dashboard.html       # Role-based dashboard
│   └── notifications.html   # Notification center
│
├── 📁 static/               # Static files
│   ├── css/                 # Tailwind CSS
│   ├── js/                  # JavaScript files
│   └── images/              # Images & icons
│
├── 📁 pms_system/           # Project configuration
│   ├── settings.py          # Django settings
│   ├── urls.py              # URL configuration
│   └── wsgi.py              # WSGI config
│
└── 📄 manage.py             # Django management script


💻 Usage Guide
👑 Admin Dashboard
    User Management: Add/Edit/Delete users, assign roles
    
    Department Setup: Create departments and designations

    Project Oversight: Monitor all projects and tasks

    System Configuration: Manage global settings

👔 Team Lead Dashboard
    Task Assignment: Assign tasks to team members

    Progress Tracking: Monitor task status and deadlines

    Team Management: View team performance metrics

    Notifications: Receive updates on task completions

👩‍💻 Employee Dashboard
    My Tasks: View assigned tasks with deadlines

    Task Updates: Start/Complete tasks with timers

    Notifications: Get real-time task assignments

    Progress View: Track personal productivity


Notification Dropdown

┌──────────────────────────────┐
│ 🔔 Notifications         (3) │
├──────────────────────────────┤
│ 📌 New task assigned:        │
│    "Fix login bug"           │
│    🕐 5 minutes ago          │
├──────────────────────────────┤
│ ✅ Task completed:           │
│    "Database migration"      │
│    by John Doe               │
│    🕐 1 hour ago             │
├──────────────────────────────┤
│ ⏯️ Task started:             │
│    "API development"         │
│    by Jane Smith             │
│    🕐 2 hours ago            │
├──────────────────────────────┤
│      📄 View all notifications│
└──────────────────────────────┘




