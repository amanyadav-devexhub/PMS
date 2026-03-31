from django.urls import path,include
from . import views
from Tasks.models import Task
from Tasks.forms import TaskForm
from django.contrib.auth import views as auth_views

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    login_view,
    admin_dashboard,
    teamlead_dashboard,
    employee_dashboard,
    login_page,
)

urlpatterns = [

    ## user manamgement
    path("user/create/", views.create_user, name="create_user"),
    path("user/<int:user_id>/delete/", views.delete_user, name="delete_user"),
    path("user/<int:user_id>/edit/", views.edit_user, name='edit_user'),
    path("user/<int:user_id>/",views.view_user_details,name="view_user_details"),
    path('user/check-email-exists/', views.check_email_exists, name='check_email_exists'),

    # User listing endpoints (role-based)
    path("users/admin/", views.admin_view_users, name='admin_view_users'),
    path("users/teamlead/", views.teamlead_view_users, name='teamlead_view_users'),


    # Project management endpoints
    path("project/create/", views.create_project, name="create_project"),
    path("projects/",views.view_projects,name="view_projects"),
    path("project/<int:project_id>/edit/", views.edit_projects, name='edit_projects'),
    path("project/<int:id>/delete/", views.delete_project, name='delete_project'),
    path("project/<int:project_id>/", views.view_project_detail, name="view_project_detail"),
    path("project/<int:project_id>/resource/add/", views.add_project_resource, name="add_project_resource"),

    # Employee-specific views
    path("employee/projects/", views.employee_projects, name='employee_projects'),
    path("employee/tasks/", views.employee_tasks, name='employee_tasks'), ## pending

    # Task management endpoints
    path("task/assign/", views.assign_task, name="assign_task"), 
    path("task/<int:task_id>/start/", views.start_task, name='start_task'),
    path("task/<int:task_id>/pause/", views.pause_task, name='pause_task'),
    path("task/<int:task_id>/resume/", views.resume_task, name='resume_task'),
    path("task/<int:task_id>/complete/", views.complete_task, name='complete_task'),
    path("task/<int:task_id>/edit/", views.edit_task, name='edit_task'),
    path("task/<int:task_id>/delete/", views.delete_task, name='delete_task'),
    path("task/<int:task_id>/summary/add/", views.add_task_summary, name='add_task_summary'),
    path("tasks/my/", views.task_dashboard, name='task_dashboard'),

    ## Department management endpoints
    path("departments/", views.departments, name='departments'),
    path("department/<int:dept_id>/", views.department_detail, name='department_detail'),
    path("department/create/", views.create_department, name='create_department'),
    path("department/<int:dept_id>/delete/", views.delete_department, name='delete_department'),

    # Designation management endpoints
    path("designations/", views.designations, name='designations'),
    path("designation/<int:desig_id>/", views.designation_detail, name='designation_detail'),
    path("designation/create/", views.create_designation, name='create_designation'),
    path("designation/<int:desig_id>/delete/", views.delete_designation, name='delete_designation'),

    # Authentication endpoints
    path("login/", login_page, name="login_page"),
    path("ajax_login/", views.ajax_login, name="ajax_login"),
    path("logout/", views.logout_view, name='logout'),
    path("password/reset/", auth_views.PasswordResetView.as_view(template_name='password_reset.html'), name='reset_password'),
    path("password/reset/done/", auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path("password/reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),


    # Dashboard and analytics
    path("dashboard/", views.dashboard, name='dashboard'),
    path("analytics/user/", views.user_analytics, name='user_analytics'),

    # Notifications
    path("notifications/", include('notifications.urls')),

    ## Api tokens
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    ## home page
    path('', views.home, name='home'),





    #path("login/", login_view, name="login"),
    # path('', views.home, name='home'),
   
    path("admin_dashboard/", admin_dashboard, name="admin_dashboard"),
    path("teamlead_dashboard/", teamlead_dashboard, name="teamlead_dashboard"),
    path("employee_dashboard/", employee_dashboard, name="employee_dashboard"),
    path("register/", views.register, name="register"),
    # path("user/create/", views.create_user, name="create_user"),
    # path("user/<int:user_id>/delete/", views.delete_user, name="delete_user"),
    # path("create_project/", views.create_project, name="create_project"),
    # path("assign_task/", views.assign_task, name="assign_task"),
    # path('logout/', views.logout_view, name='logout'),
    # path('employee_tasks/', views.employee_tasks, name='employee_tasks'),
    # path('update_task/<int:task_id>/', views.update_task_status, name='update_task_status'),
    # path('reset_password/',auth_views.PasswordResetView.as_view(template_name='password_reset.html'),name='reset_password'),
    # path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    # path('reset/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    # path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path('check-email-exists/', views.check_email_exists, name='check_email_exists'),
    # path("activate/<uidb64>/<token>/", views.activate_user, name="activate"),

    path('dashboard/', views.dashboard, name='dashboard'),
    # path('admin-view-users/', views.admin_view_users, name='admin_view_users'),
    # path('teamlead-view-users/', views.teamlead_view_users, name='teamlead_view_users'),
    # path("ajax_login/", views.ajax_login, name="ajax_login"),
    # path("login/", login_page, name="login_page"),
    # path("view_projects/",views.view_projects,name="view_projects"),
    # path("edit_projects/<int:project_id>/",views.edit_projects,name='edit_projects'),
    # path("delete_project/<int:id>/",views.delete_project,name = 'delete_project'),
    # path("view_project_detail/<int:project_id>/",views.view_project_detail,name = "view_project_detail"),
    # path("view_user_details/<int:user_id>/",views.view_user_details,name="view_user_details"),
    # path("project/<int:project_id>/add-resource/",views.add_project_resource,name="add_project_resource"),
    # path('employee_projects/', views.employee_projects, name='employee_projects'),
    # path('departments/', views.departments, name='departments'),
    # path('department_detail/<int:dept_id>/', views.department_detail, name='department_detail'),
    # path('designations/', views.designations, name='designations'),
    # path('designation_detail/<int:desig_id>/', views.designation_detail, name='designation_detail'),
    # path('department/create/', views.create_department, name='create_department'),
    # path('department/delete/<int:dept_id>/', views.delete_department, name='delete_department'),
    # path('designation/delete/<int:desig_id>/', views.delete_designation, name='delete_designation'),
    # path('designation/create/', views.create_designation, name='create_designation'),    

    # path('notifications/', include('notifications.urls')),
    # path('task/<int:task_id>/start/', views.start_task, name='start_task'),
    # path('task/<int:task_id>/pause/', views.pause_task, name='pause_task'),
    # path('task/<int:task_id>/resume/', views.resume_task, name='resume_task'),
    # path('task/<int:task_id>/complete/', views.complete_task, name='complete_task'),
    # path('my-tasks/', views.task_dashboard, name='task_dashboard'),
    # path('task/<int:task_id>/edit/', views.edit_task, name='edit_task'),
    # path('task/<int:task_id>/delete/', views.delete_task, name='delete_task'),
    # path('task/<int:task_id>/add-summary/', views.add_task_summary, name='add_task_summary'),
    # path('user-analytics/', views.user_analytics, name='user_analytics'),
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
]










