# users/decorators.py
from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.contrib.auth import get_user_model

User = get_user_model()

def jwt_required(view_func):
    """
    Decorator that REQUIRES JWT authentication.
    Accepts token from Authorization header or access_token cookie.
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = None

        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()

        if not token:
            token = request.COOKIES.get('access_token')

        if not token:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required. Please login again.'
                }, status=401)
            return redirect(reverse('login_page'))

        auth = JWTAuthentication()
        try:
            validated_token = auth.get_validated_token(token)
            user = auth.get_user(validated_token)

            if user is None or not user.is_active:
                raise AuthenticationFailed('Invalid or inactive user.')

            request.user = user
        except (InvalidToken, AuthenticationFailed, Exception):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid or expired token. Please login again.'
                }, status=401)
            response = redirect(reverse('login_page'))
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            return response

        return view_func(request, *args, **kwargs)
    
    return wrapped_view


# Backward-compatible alias for existing views.
jwt_or_session_required = jwt_required


def allowed_roles(allowed_roles=[]):
    """
    Role-based access control decorator
    Works with both session and JWT authentication
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required'
                }, status=401)
            
            if request.user.role not in allowed_roles and not request.user.is_superuser:
                return JsonResponse({
                    'success': False,
                    'error': f'Access denied. Required role: {", ".join(allowed_roles)}. Your role: {request.user.role}'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator