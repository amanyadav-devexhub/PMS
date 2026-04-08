from django.urls import path
from . import views

urlpatterns = [
    # Auth endpoints
    path('auth/login/', views.LoginAPIView.as_view(), name='api_login'),
    path('auth/refresh/', views.RefreshAPIView.as_view(), name='api_refresh'),
    path('auth/logout/', views.LogoutAPIView.as_view(), name='api_logout'),
    path('auth/me/', views.MeAPIView.as_view(), name='api_me'),

    # Resource endpoints
    path('projects/', views.ProjectListAPIView.as_view(), name='api_projects'),
    path('projects/<int:pk>/', views.ProjectDetailAPIView.as_view(), name='api_project_detail'),
    path('users/', views.UserListAPIView.as_view(), name='api_users'),
    path('tasks/', views.TaskListAPIView.as_view(), name='api_tasks'),
    path('tasks/<int:pk>/', views.TaskDetailAPIView.as_view(), name='api_task_detail'),
    path('api/dashboard/', views.DashboardAPIView.as_view(), name='api_dashboard'),
]
