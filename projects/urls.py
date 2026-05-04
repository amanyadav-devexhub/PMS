from django.urls import include, path
from . import views

urlpatterns = [
    # =========================================================================
    # PROJECT MANAGEMENT ENDPOINTS
    # =========================================================================
    path("project/create/", views.create_project, name="create_project"),
    path("projects/", views.view_projects, name="view_projects"),
    path("project/<int:project_id>/edit/", views.edit_projects, name='edit_projects'),
    path("project/<int:project_id>/", views.view_project_detail, name="view_project_detail"),
    path("project/<int:project_id>/resource/add/", views.add_project_resource, name="add_project_resource"),
    path("employee/projects/", views.employee_projects, name='employee_projects'),
    # =========================================================================
    # API ENDPOINTS (REST API)
    # =========================================================================
    path('api/projects/', include('projects.api.urls')),
]
