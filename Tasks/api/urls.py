from django.urls import path
from . import views

urlpatterns = [
    path('', views.TaskListAPIView.as_view(), name='api_tasks'),
    path('<int:pk>/', views.TaskDetailAPIView.as_view(), name='api_task_detail'),
]