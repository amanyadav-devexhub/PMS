from django.urls import include, path
from . import views


urlpatterns = [
    # =========================================================================
    # TASK ASSIGNMENT & CREATION
    # =========================================================================
    
    path("task/assign/", views.assign_task, name="assign_task"),

    # =========================================================================
    # TASK WORKFLOW (State Management)
    # =========================================================================
    
    
    path("task/<int:task_id>/start/", views.start_task, name='start_task'),
    path("task/<int:task_id>/pause/", views.pause_task, name='pause_task'),
    path("task/<int:task_id>/resume/", views.resume_task, name='resume_task'),
    path("task/<int:task_id>/complete/", views.complete_task, name='complete_task'),
  
    # =========================================================================
    # TASK MANAGEMENT (CRUD Operations)
    # =========================================================================
    
    path("task/<int:task_id>/edit/", views.edit_task, name='edit_task'),
    path("task/<int:task_id>/summary/add/", views.add_task_summary, name='add_task_summary'),
   
    # =========================================================================
    # TASK VIEWS & DASHBOARDS
    # =========================================================================
    
    path("tasks/my/", views.task_dashboard, name='task_dashboard'),
   
    # =========================================================================
    # API ENDPOINTS (REST API)
    # =========================================================================
    
    path('api/tasks/', include('Tasks.api.urls')),
    path("employee/tasks/", views.employee_tasks, name='employee_tasks'),
]

