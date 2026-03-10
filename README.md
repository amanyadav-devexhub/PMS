Project Management System (PMS)

A web-based Project Management System built with Django, Tailwind CSS, and PostgreSQL/SQLite that allows Admins, Team Leads, and Employees to manage projects, tasks, and notifications efficiently.

Table of Contents

Features

Tech Stack

Installation

Project Structure

Usage

Notifications

Screenshots

Contributing

License

Features

User Roles:

Admin: Manage members, projects, departments, and designations.

Team Lead: Assign tasks to employees, track progress.

Employee: View tasks, start/complete tasks, see notifications.

Task Management:

Create, assign, and track tasks with start/end dates and timers.

Task status: PENDING, ONGOING, COMPLETED.

Notification System:

Real-time notifications for task assignments, start, and completion.

Notification bell with unread count and dropdown for latest notifications.

View all notifications and mark them as read.

Dashboard:

Role-based dashboards showing relevant tasks and projects.

Authentication:

JWT-based login for secure API access.

Role-based access control for views.

Tech Stack

Backend: Django 6.0

Frontend: Tailwind CSS, HTML, JavaScript

Database: SQLite (default) / PostgreSQL

Python Version: 3.14+

Installation

Clone the repository

git clone https://github.com/yourusername/pms_system.git
cd pms_system

Create a virtual environment

python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

Install dependencies

pip install -r requirements.txt

Apply migrations

python manage.py makemigrations
python manage.py migrate

Create a superuser

python manage.py createsuperuser

Run the development server

python manage.py runserver

Open in browser

http://127.0.0.1:8000/
Project Structure
pms_system/
├── users/               # User management (roles, authentication)
├── projects/            # Projects and related models
├── notifications/       # Notifications system (model, views, templates)
├── templates/           # Global templates
├── static/              # Static files (CSS, JS, images)
├── pms_system/          # Project settings
└── manage.py            # Django management script
Usage

Admin: Manage users, departments, designations, and projects.

Team Lead: Assign tasks to employees, track task progress.

Employee: Start and complete tasks, view notifications.

Notifications

Notification Bell: Shows unread notifications in the top bar.

Dropdown Panel: Latest 5 notifications appear in a dropdown.

All Notifications Page: See all notifications and mark them as read.

Notification triggers:

Task assigned → sends notification to the assigned employee.

Task started → sends notification to Admins & Team Leads.

Task completed → sends notification to Admins & Team Leads.

Screenshots

Dashboard


Notification Dropdown


All Notifications Page
