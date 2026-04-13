from django.urls import include, path
from . import views


urlpatterns = [
    # =========================================================================
    # TASK ASSIGNMENT & CREATION
    # =========================================================================
    
    path("task/assign/", views.assign_task, name="assign_task"),
    # Purpose: Assign new task to employees
    # Permissions: Tasks.add_task
    # Method: GET (form), POST (submit)
    # Template: assign_task.html
    
    # =========================================================================
    # TASK WORKFLOW (State Management)
    # =========================================================================
    
    path("task/<int:task_id>/start/", views.start_task, name='start_task'),
    # Purpose: Start a pending task (changes status to ONGOING)
    # Permissions: Tasks.change_task
    # Method: POST (AJAX)
    # Returns: JSON response
    
    path("task/<int:task_id>/pause/", views.pause_task, name='pause_task'),
    # Purpose: Pause an ongoing task
    # Permissions: Tasks.change_task
    # Method: POST (AJAX)
    # Returns: JSON response
    
    path("task/<int:task_id>/resume/", views.resume_task, name='resume_task'),
    # Purpose: Resume a paused task
    # Permissions: Tasks.change_task
    # Method: POST (AJAX)
    # Returns: JSON response
    
    path("task/<int:task_id>/complete/", views.complete_task, name='complete_task'),
    # Purpose: Complete a task (requires summary first)
    # Permissions: Tasks.change_task
    # Method: POST (AJAX)
    # Returns: JSON response
    
    # =========================================================================
    # TASK MANAGEMENT (CRUD Operations)
    # =========================================================================
    
    path("task/<int:task_id>/edit/", views.edit_task, name='edit_task'),
    # Purpose: Edit existing task details
    # Access: Task owner OR project creator
    # Permissions: Tasks.change_task
    # Method: GET (form), POST (submit)
    # Template: edit_task.html
    
    path("task/<int:task_id>/delete/", views.delete_task, name='delete_task'),
    # Purpose: Soft delete task (moves to trash)
    # Access: Task owner OR project creator
    # Permissions: Tasks.delete_task
    # Method: POST
    # Returns: JSON or redirect
    
    path("task/<int:task_id>/summary/add/", views.add_task_summary, name='add_task_summary'),
    # Purpose: Add completion summary to task
    # Access: Assigned employee only
    # Permissions: Tasks.change_task
    # Method: POST (AJAX), GET (form)
    # Template: add_task_summary.html
    
    # =========================================================================
    # TASK VIEWS & DASHBOARDS
    # =========================================================================
    
    path("tasks/my/", views.task_dashboard, name='task_dashboard'),
    # Purpose: View all tasks (role-based filtered)
    # Permissions: Tasks.view_task
    # Method: GET
    # Template: task_dashboard.html
    
    # =========================================================================
    # API ENDPOINTS (REST API)
    # =========================================================================
    
    path('api/tasks/', include('Tasks.api.urls')),
    # Purpose: REST API endpoints for tasks
    # Includes: List, Create, Retrieve, Update, Delete operations
    # Format: JSON responses
    path("employee/tasks/", views.employee_tasks, name='employee_tasks'),
]

# =========================================================================
# URL PATTERN SUMMARY
# =========================================================================
# Total URLs: 9 main + 1 API include
# 
# ┌─────────────────────────────┬─────────────────────────────────────────┐
# │ URL Pattern                 │ Purpose                                 │
# ├─────────────────────────────┼─────────────────────────────────────────┤
# │ /task/assign/               │ Assign new task form                    │
# │ /task/<id>/start/           │ Start task (AJAX)                       │
# │ /task/<id>/pause/           │ Pause task (AJAX)                       │
# │ /task/<id>/resume/          │ Resume task (AJAX)                      │
# │ /task/<id>/complete/        │ Complete task (AJAX)                    │
# │ /task/<id>/edit/            │ Edit task form                          │
# │ /task/<id>/delete/          │ Soft delete task                        │
# │ /task/<id>/summary/add/     │ Add completion summary                  │
# │ /tasks/my/                  │ Task dashboard                          │
# │ /api/tasks/                 │ REST API endpoints                      │
# └─────────────────────────────┴─────────────────────────────────────────┘