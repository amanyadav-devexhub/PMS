from django.urls import path
from . import views
from . import functional_views

urlpatterns = [
    # Main chatbot page
    path('', views.chatbot_page, name='chatbot_page'),
    
    # API endpoint for sending messages
    path('api/chat/', views.chat_api, name='chat_api'),

    # Functional Dashboard Bot
    path('dashboard-bot/', functional_views.dashboard_bot_page, name='dashboard_bot_page'),
    path('dashboard-bot/api/', functional_views.dashboard_bot_api, name='dashboard_bot_api'),
]