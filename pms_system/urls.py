"""
URL configuration for pms_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # =========================================================================
    # HTML VIEWS (No prefixes - let each app handle its own routing)
    # =========================================================================
    path("", include("users.urls")),      # Users app (home, login, dashboard, user management)
    path("", include("projects.urls")),   # Projects app (project CRUD)
    path("", include("Tasks.urls")),      # Tasks app (task CRUD, workflow)
    path("chat/", include("chat.urls")),  # Chat app
    
    # =========================================================================
    # API ENDPOINTS (All under /api/)
    # =========================================================================
    path('api/', include('users.api.urls')),           # Auth, dashboard, users API
    path('api/projects/', include('projects.api.urls')), # Projects API
    path('api/tasks/', include('Tasks.api.urls')),     # Tasks API
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
