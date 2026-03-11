from django.urls import path,include
from . import views
from Tasks.models import Task
from Tasks.forms import TaskForm
from django.contrib.auth import views as auth_views



from .views import (
    login_view,
    admin_dashboard,
    teamlead_dashboard,
    employee_dashboard,
    login_page,
)

urlpatterns = [
    #path("login/", login_view, name="login"),
    path('', views.home, name='home'),
    path("admin_dashboard/", admin_dashboard, name="admin_dashboard"),
    path("teamlead_dashboard/", teamlead_dashboard, name="teamlead_dashboard"),
    path("employee_dashboard/", employee_dashboard, name="employee_dashboard"),
    path("register/", views.register, name="register"),
    path("create_user/", views.create_user, name="create_user"),
    path("delete_user/<int:user_id>/", views.delete_user, name="delete_user"),
    path("create_project/", views.create_project, name="create_project"),
    path("assign_task/", views.assign_task, name="assign_task"),
    path('logout/', auth_views.LogoutView.as_view(next_page='login_page'), name='logout'),
    path('employee_tasks/', views.employee_tasks, name='employee_tasks'),
    path('update_task/<int:task_id>/', views.update_task_status, name='update_task_status'),
    path('reset_password/',auth_views.PasswordResetView.as_view(template_name='password_reset.html'),name='reset_password'),
    path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path("activate/<uidb64>/<token>/", views.activate_user, name="activate"),
    path('reset_password_complete/',auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),name='password_reset_complete'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('admin-view-users/', views.admin_view_users, name='admin_view_users'),
    path('teamlead-view-users/', views.teamlead_view_users, name='teamlead_view_users'),
    path("ajax_login/", views.ajax_login, name="ajax_login"),
    path("render_login/", login_page, name="login_page"),
    path("view_projects/",views.view_projects,name="view_projects"),
    path("edit_projects/<int:project_id>/",views.edit_projects,name='edit_projects'),
    path("delete_project/<int:id>/",views.delete_project,name = 'delete_project'),
    path("view_project_detail/<int:project_id>/",views.view_project_detail,name = "view_project_detail"),
    path("view_user_details/<int:user_id>/",views.view_user_details,name="view_user_details"),
    path(
        "project/<int:project_id>/add-resource/",
        views.add_project_resource,
        name="add_project_resource"
    ),
    path('employee_projects/', views.employee_projects, name='employee_projects'),
    path('departments/', views.departments, name='departments'),
    path('department_detail/<int:dept_id>/', views.department_detail, name='department_detail'),
    path('designations/', views.designations, name='designations'),
    path('designation_detail/<int:desig_id>/', views.designation_detail, name='designation_detail'),
    path('department/create/', views.create_department, name='create_department'),
    path('department/delete/<int:dept_id>/', views.delete_department, name='delete_department'),
    path('designation/delete/<int:desig_id>/', views.delete_designation, name='delete_designation'),
    path('designation/create/', views.create_designation, name='create_designation'),    
    path("start_task/<int:task_id>/", views.start_task, name="start_task"),
    path("complete_task/<int:task_id>/", views.complete_task, name="complete_task"),
    path('notifications/', include('notifications.urls')),
]







