from django.urls import path
from . import views

urlpatterns = [
    path('auth/login/', views.LoginAPIView.as_view(), name='api_login'),
    path('auth/refresh/', views.RefreshAPIView.as_view(), name='api_refresh'),
    path('auth/logout/', views.LogoutAPIView.as_view(), name='api_logout'),
    path('auth/me/', views.MeAPIView.as_view(), name='api_me'),
    path('users/', views.UserListAPIView.as_view(), name='api_users'),
    path('dashboard/', views.DashboardAPIView.as_view(), name='api_dashboard'),
    path('users/<int:user_id>/', views.UserDetailAPIView.as_view(), name='api_user_detail'),
    path('analytics/', views.UserAnalyticsAPIView.as_view(), name='api_analytics'),
    path('departments/', views.DepartmentListAPIView.as_view(), name='api_departments'),
    path('designations/', views.DesignationListAPIView.as_view(), name='api_designations'),
]
