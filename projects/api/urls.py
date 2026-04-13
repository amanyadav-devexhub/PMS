from django.urls import path
from . import views

urlpatterns = [

    path('', views.ProjectListAPIView.as_view(), name='api_projects'),
    path('<int:pk>/', views.ProjectDetailAPIView.as_view(), name='api_project_detail'),
]