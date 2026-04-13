from django.urls import path
from . import views

urlpatterns = [
    # Auth endpoints
    path('auth/login/', views.LoginAPIView.as_view(), name='api_login'),
    path('auth/refresh/', views.RefreshAPIView.as_view(), name='api_refresh'),
    path('auth/logout/', views.LogoutAPIView.as_view(), name='api_logout'),
    path('auth/me/', views.MeAPIView.as_view(), name='api_me'),
    path('users/', views.UserListAPIView.as_view(), name='api_users'),
    path('api/dashboard/', views.DashboardAPIView.as_view(), name='api_dashboard'),
]
