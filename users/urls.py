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
    login_page,
)

urlpatterns = [

    # =========================================================================
    # USER MANAGEMENT (CRUD Operations)
    # =========================================================================
    path("user/create/", views.create_user, name="create_user"),
    path("user/<int:user_id>/delete/", views.delete_user, name="delete_user"),
    path("user/<int:user_id>/edit/", views.edit_user_page, name='edit_user_page'),
    path("user/<int:user_id>/details/", views.get_user_details, name='get_user_details'),
    path("user/<int:user_id>/update/", views.update_user, name='update_user'),
    path("user/<int:user_id>/", views.view_user_details, name="view_user_details"),
    path('user/check-email-exists/', views.check_email_exists, name='check_email_exists'),
    # =========================================================================
    # ROLE MANAGEMENT
    # =========================================================================
    path("roles/", views.role_list, name="role_list"),
    path("roles/create/", views.role_create, name="role_create"),
    path("roles/<int:role_id>/edit/", views.role_edit, name="role_edit"),
    path("roles/<int:role_id>/delete/", views.role_delete, name="role_delete"),
    # ========================================================================
    # PERMISSION MANAGEMENT
    # =========================================================================
    path("permissions/", views.permission_list, name="permission_list"),
    path("permissions/create/", views.permission_create, name="permission_create"),
    path("permissions/<int:perm_id>/delete/", views.permission_delete, name="permission_delete"),
    # =========================================================================
    # USER LISTING (Role-based views)
    # =========================================================================
    path("users/admin/", views.admin_view_users, name='admin_view_users'),
    path("users/teamlead/", views.teamlead_view_users, name='teamlead_view_users'),
    # =========================================================================
    # DEPARTMENT MANAGEMENT
    # =========================================================================
    path("departments/", views.departments, name='departments'),
    path("department/<int:dept_id>/", views.department_detail, name='department_detail'),
    path("department/<int:dept_id>/members/api/", views.department_members_api, name='department_members_api'),
    path("department/create/", views.create_department, name='create_department'),
    path("department/<int:dept_id>/delete/", views.delete_department, name='delete_department'),
    # =========================================================================
    # DESIGNATION MANAGEMENT
    # =========================================================================
    path("designations/", views.designations, name='designations'),
    path("designation/<int:desig_id>/", views.designation_detail, name='designation_detail'),
    path("designation/<int:desig_id>/members/api/", views.designation_members_api, name='designation_members_api'),
    path("designation/create/", views.create_designation, name='create_designation'),
    path("designation/<int:desig_id>/delete/", views.delete_designation, name='delete_designation'),
    # =========================================================================
    # AUTHENTICATION ENDPOINTS
    # =========================================================================
    path("login/", login_page, name="login_page"),
    path("ajax_login/", views.ajax_login, name="ajax_login"),
    path("logout/", views.logout_view, name='logout'),
    path("password/reset/", auth_views.PasswordResetView.as_view(template_name='reset_password/password_reset.html'), name='reset_password'),
    path("password/reset/done/", auth_views.PasswordResetDoneView.as_view(template_name='reset_password/password_reset_done.html'), name='password_reset_done'),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name='reset_password/password_reset_confirm.html'), name='password_reset_confirm'),
    path("password/reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name='reset_password/password_reset_complete.html'), name='password_reset_complete'),
    # =========================================================================
    # DASHBOARD & ANALYTICS
    # =========================================================================
    path("dashboard/", views.dashboard, name='dashboard'),
    path("analytics/user/", views.user_analytics, name='user_analytics'),
    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================
    path("notifications/", include('notifications.urls')),
    # =========================================================================
    # EMAIL VERIFICATION & ACTIVATION
    # =========================================================================
    path('check-email-exists/', views.check_email_exists, name='check_email_exists'),
    path("activate/<uidb64>/<token>/", views.activate_user, name="activate"),
    # =========================================================================
    # API TOKENS (JWT)
    # =========================================================================
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # =========================================================================
    # USER PROFILE
    # =========================================================================
    path('my-profile/', views.my_profile, name='my_profile'),
    # =========================================================================
    # HOME PAGE
    # =========================================================================
    path('', views.home, name='home'),
    # =========================================================================
    # TRASH MANAGEMENT (Soft-deleted items)
    # =========================================================================
    path('trash/', views.trash_view, name='trash_view'),
    path('trash/restore/<str:item_type>/<int:item_id>/', views.restore_item, name='restore_item'),
    path('trash/permanent/<str:item_type>/<int:item_id>/', views.permanent_delete_item, name='permanent_delete_item'),
    # =========================================================================
    # ACTIVITY LOGS
    # =========================================================================
    path('activity-log/<int:project_id>/', views.activity_log_view, name='activity_log_view'),
    path('activity-log/', views.activity_log_view, name='activity_log_all'), 


    # =========================================================================
    # PERMISSION OVERRIDES MANAGEMENT
    # =========================================================================
    path("permission-overrides/", views.permission_overrides, name="permission_overrides"),
    path("permission-overrides/api/", views.get_permission_overrides, name="get_permission_overrides"),
    path("permission-overrides/create/", views.create_permission_override, name="create_permission_override"),
    path("permission-overrides/<int:override_id>/delete/", views.delete_permission_override, name="delete_permission_override"),
    path("permission-overrides/sync/", views.sync_permission_overrides, name="sync_permission_overrides"),
    path("api/permissions/all/", views.get_all_permissions, name="get_all_permissions"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    