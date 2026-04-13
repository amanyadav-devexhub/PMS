from django.urls import path, include
from pms_system import settings
from . import views
from Tasks.models import Task
from Tasks.forms import TaskForm
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    login_view,
    login_page,
)

urlpatterns = [

    # =========================================================================
    # USER MANAGEMENT (CRUD Operations)
    # =========================================================================
    
    path("user/create/", views.create_user, name="create_user"),
    # Purpose: Create new user (Admin only)
    # Method: GET (form), POST (submit)
    # Template: create_user.html
    
    path("user/<int:user_id>/delete/", views.delete_user, name="delete_user"),
    # Purpose: Delete user (Admin only)
    # Method: POST
    # Redirects to admin_dashboard
    
    path("user/<int:user_id>/edit/", views.edit_user_page, name='edit_user_page'),
    # Purpose: Display edit user form (Admin only)
    # Method: GET
    # Template: edit_user.html
    
    path("user/<int:user_id>/details/", views.get_user_details, name='get_user_details'),
    # Purpose: Get user details as JSON (Admin only)
    # Method: GET
    # Returns: JSON response with user data
    
    path("user/<int:user_id>/update/", views.update_user, name='update_user'),
    # Purpose: Update user details (Admin only)
    # Method: POST
    # Returns: JSON or redirect
    
    path("user/<int:user_id>/", views.view_user_details, name="view_user_details"),
    # Purpose: View single user profile
    # Method: GET, POST (self-edit)
    # Access: Own profile OR users.view_user permission
    # Template: view_user_details.html
    
    path('user/check-email-exists/', views.check_email_exists, name='check_email_exists'),
    # Purpose: Check if email already registered (Public endpoint)
    # Method: POST
    # Returns: JSON {exists: true/false}


    # =========================================================================
    # ROLE MANAGEMENT
    # =========================================================================
    
    path("roles/", views.role_list, name="role_list"),
    # Purpose: List all roles
    # Permissions: users.view_role, users.add_role, users.change_role
    # Template: role_list.html
    
    path("roles/create/", views.role_create, name="role_create"),
    # Purpose: Create new role
    # Permissions: users.add_role
    # Template: role_form.html
    
    path("roles/<int:role_id>/edit/", views.role_edit, name="role_edit"),
    # Purpose: Edit existing role
    # Permissions: users.change_role
    # Template: role_form.html
    
    path("roles/<int:role_id>/delete/", views.role_delete, name="role_delete"),
    # Purpose: Delete role (with fallback assignment)
    # Permissions: users.delete_role
    # Method: POST


    # =========================================================================
    # PERMISSION MANAGEMENT
    # =========================================================================
    
    path("permissions/", views.permission_list, name="permission_list"),
    # Purpose: List all Django permissions
    # Permissions: auth.view_permission, auth.add_permission
    # Template: permission_list.html
    
    path("permissions/create/", views.permission_create, name="permission_create"),
    # Purpose: Create custom permission
    # Permissions: auth.add_permission
    # Template: permission_form.html
    
    path("permissions/<int:perm_id>/delete/", views.permission_delete, name="permission_delete"),
    # Purpose: Delete permission
    # Permissions: auth.delete_permission
    # Method: POST


    # =========================================================================
    # USER LISTING (Role-based views)
    # =========================================================================
    
    path("users/admin/", views.admin_view_users, name='admin_view_users'),
    # Purpose: Admin view - list all users
    # Permissions: users.view_user, users.add_user, users.change_user, users.delete_user
    # Template: admin_view_users.html
    
    path("users/teamlead/", views.teamlead_view_users, name='teamlead_view_users'),
    # Purpose: Team Lead view - list only contributors
    # Permissions: users.view_user + Tasks.add_task
    # Template: teamlead_view_users.html


    # =========================================================================
    # EMPLOYEE-SPECIFIC VIEWS
    # =========================================================================
    
    path("employee/projects/", views.employee_projects, name='employee_projects'),
    # Purpose: Employee project listing with filters
    # Permissions: projects.view_projects
    # Template: employee_projects.html


    # =========================================================================
    # DEPARTMENT MANAGEMENT
    # =========================================================================
    
    path("departments/", views.departments, name='departments'),
    # Purpose: List all departments
    # Permissions: users.view_department, users.add_department, etc.
    # Template: department_list.html
    
    path("department/<int:dept_id>/", views.department_detail, name='department_detail'),
    # Purpose: View department details and members
    # Template: department_detail.html
    
    path("department/<int:dept_id>/members/api/", views.department_members_api, name='department_members_api'),
    # Purpose: AJAX endpoint for department members
    # Permissions: users.view_department
    # Returns: JSON with users list
    
    path("department/create/", views.create_department, name='create_department'),
    # Purpose: Create new department
    # Permissions: users.add_department
    # Template: create_department.html
    
    path("department/<int:dept_id>/delete/", views.delete_department, name='delete_department'),
    # Purpose: Delete department
    # Permissions: users.delete_department
    # Method: POST


    # =========================================================================
    # DESIGNATION MANAGEMENT
    # =========================================================================
    
    path("designations/", views.designations, name='designations'),
    # Purpose: List all designations
    # Permissions: users.view_designation, users.add_designation, etc.
    # Template: designation_list.html
    
    path("designation/<int:desig_id>/", views.designation_detail, name='designation_detail'),
    # Purpose: View designation details and members
    # Template: designation_detail.html
    
    path("designation/<int:desig_id>/members/api/", views.designation_members_api, name='designation_members_api'),
    # Purpose: AJAX endpoint for designation members
    # Permissions: users.view_designation
    # Returns: JSON with users list
    
    path("designation/create/", views.create_designation, name='create_designation'),
    # Purpose: Create new designation
    # Permissions: users.add_designation
    # Template: designation_form.html
    
    path("designation/<int:desig_id>/delete/", views.delete_designation, name='delete_designation'),
    # Purpose: Delete designation
    # Permissions: users.delete_designation
    # Method: POST


    # =========================================================================
    # AUTHENTICATION ENDPOINTS
    # =========================================================================
    
    path("login/", login_page, name="login_page"),
    # Purpose: Display login page
    # Template: ajax_login.html
    
    path("ajax_login/", views.ajax_login, name="ajax_login"),
    # Purpose: JWT login endpoint for AJAX/API
    # Method: POST
    # Returns: JSON with access_token, refresh_token
    
    path("logout/", views.logout_view, name='logout'),
    # Purpose: Logout user (blacklist JWT token)
    # Method: POST/GET
    # Clears JWT cookies
    
    path("password/reset/", auth_views.PasswordResetView.as_view(template_name='password_reset.html'), name='reset_password'),
    # Purpose: Password reset request form
    # Template: password_reset.html
    
    path("password/reset/done/", auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    # Purpose: Password reset email sent confirmation
    # Template: password_reset_done.html
    
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    # Purpose: Set new password form
    # Template: password_reset_confirm.html
    
    path("password/reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    # Purpose: Password reset success page
    # Template: password_reset_complete.html


    # =========================================================================
    # DASHBOARD & ANALYTICS
    # =========================================================================
    
    path("dashboard/", views.dashboard, name='dashboard'),
    # Purpose: Main dashboard (role-based view)
    # Authentication: JWT or session required
    # Template: dashboard.html
    
    path("analytics/user/", views.user_analytics, name='user_analytics'),
    # Purpose: User performance analytics
    # Permissions: Tasks.view_task OR users.view_user
    # Template: user_analytics.html


    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================
    
    path("notifications/", include('notifications.urls')),
    # Purpose: Include notification app URLs


    # =========================================================================
    # EMAIL VERIFICATION & ACTIVATION
    # =========================================================================
    
    path('check-email-exists/', views.check_email_exists, name='check_email_exists'),
    # Purpose: Check email existence (duplicate with above)
    # Method: POST
    # Returns: JSON
    
    path("activate/<uidb64>/<token>/", views.activate_user, name="activate"),
    # Purpose: Account activation after registration
    # Method: GET (show form), POST (set password)
    # Template: set_password.html


    # =========================================================================
    # API TOKENS (JWT)
    # =========================================================================
    
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # Purpose: Obtain JWT token pair (access + refresh)
    # Method: POST with username/password
    
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Purpose: Refresh expired access token
    # Method: POST with refresh token


    # =========================================================================
    # USER PROFILE
    # =========================================================================
    
    path('my-profile/', views.my_profile, name='my_profile'),
    # Purpose: Current user's profile page with image upload
    # Authentication: JWT or session required
    # Template: my_profile.html


    # =========================================================================
    # HOME PAGE
    # =========================================================================
    
    path('', views.home, name='home'),
    # Purpose: Public home/landing page
    # Template: home.html


    # =========================================================================
    # TRASH MANAGEMENT (Soft-deleted items)
    # =========================================================================
    
    path('trash/', views.trash_view, name='trash_view'),
    # Purpose: View soft-deleted projects and tasks
    # Permissions: projects.view_projects
    # Template: trash.html
    
    path('trash/restore/<str:item_type>/<int:item_id>/', views.restore_item, name='restore_item'),
    # Purpose: Restore soft-deleted item
    # Method: POST
    # item_type: 'project' or 'task'
    
    path('trash/permanent/<str:item_type>/<int:item_id>/', views.permanent_delete_item, name='permanent_delete_item'),
    # Purpose: Permanently delete item from trash
    # Method: POST
    # item_type: 'project' or 'task'


    # =========================================================================
    # ACTIVITY LOGS
    # =========================================================================
    
    path('activity-log/<int:project_id>/', views.activity_log_view, name='activity_log_view'),
    # Purpose: View activity log for specific project
    # Access: Only project creator
    # Template: activity_log.html
    
    path('activity-log/', views.activity_log_view, name='activity_log_all'),
    # Purpose: View all activity logs (Admin only)
    # Access: Superuser only
    # Template: activity_log_all.html
]

# =========================================================================
# MEDIA FILES SERVING (Development only)
# =========================================================================

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Purpose: Serve user uploaded files (profile images) in development