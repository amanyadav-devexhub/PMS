from django.urls import path
from . import views

urlpatterns = [
    # Main chatbot page
    path('', views.chatbot_page, name='chatbot_page'),
    
    # API endpoint for sending messages
    path('api/chat/', views.chat_api, name='chat_api'),
]