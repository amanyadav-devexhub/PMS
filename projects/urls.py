from django.urls import include, path
from . import views

urlpatterns = [
    # =========================================================================
    # PROJECT MANAGEMENT ENDPOINTS
    # =========================================================================
    
    path("project/create/", views.create_project, name="create_project"),
    # Purpose: Create new project
    # Permissions: projects.add_projects or can_manage_projects
    # Method: GET (form), POST (submit)
    # Template: create_project.html
    
    path("projects/", views.view_projects, name="view_projects"),
    # Purpose: List all projects (role-based filtering)
    # Permissions: projects.view_projects
    # Method: GET
    # Template: view_projects.html
    
    path("project/<int:project_id>/edit/", views.edit_projects, name='edit_projects'),
    # Purpose: Edit existing project
    # Access: Project creator OR can_manage_projects permission
    # Method: GET (form), POST (submit)
    # Template: edit_project.html
    
    path("project/<int:id>/delete/", views.delete_project, name='delete_project'),
    # Purpose: Soft delete project (moves to trash)
    # Access: Project creator only
    # Method: POST
    # Redirects to: view_projects or trash_view
    
    path("project/<int:project_id>/", views.view_project_detail, name="view_project_detail"),
    # Purpose: View single project details with tasks
    # Permissions: projects.view_projects
    # Method: GET
    # Template: view_project_detail.html
    
    path("project/<int:project_id>/resource/add/", views.add_project_resource, name="add_project_resource"),
    # Purpose: Add resource (file/attachment) to project
    # Permissions: projects.change_projects
    # Method: POST
    # Returns: JSON or redirect
    
    # =========================================================================
    # API ENDPOINTS (REST API)
    # =========================================================================
    
    path('api/projects/', include('projects.api.urls')),
    # Purpose: REST API endpoints for projects
    # Includes: List, Create, Retrieve, Update, Delete operations
    # Format: JSON responses
]

# =========================================================================
# URL PATTERN SUMMARY
# =========================================================================
# Total URLs: 7 main + 1 API include
# 
# ┌─────────────────────────┬────────────────────────────────────────────┐
# │ URL Pattern             │ Purpose                                    │
# ├─────────────────────────┼────────────────────────────────────────────┤
# │ /project/create/        │ Create new project form                    │
# │ /projects/              │ List all projects                         │
# │ /project/<id>/edit/     │ Edit project form                          │
# │ /project/<id>/delete/   │ Soft delete project                        │
# │ /project/<id>/          │ View project details                       │
# │ /project/<id>/resource/ │ Add resource to project                    │
# │ /api/projects/          │ REST API endpoints                         │
# └─────────────────────────┴────────────────────────────────────────────┘