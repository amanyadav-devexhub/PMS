# users/decorators.py
from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.contrib import messages
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

        if token == 'null' or token == 'undefined':
            token = None

        if not token:
            token = request.COOKIES.get('access_token')

        # First, try JWT if token is present
        if token:
            try:
                auth = JWTAuthentication()
                validated_token = auth.get_validated_token(token)
                user = auth.get_user(validated_token)
                if user and user.is_active:
                    request.user = user
                    return view_func(request, *args, **kwargs)
            except Exception:
                # If JWT fails (expired, invalid), gracefully fall through to check session
                pass

        # Second, fallback to Django Session Authentication
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
            
        # Authentication totally failed
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Authentication required. Please login again.'
            }, status=401)
        
        response = redirect(reverse('login_page'))
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response

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

            current_role_name = request.user.role_obj.name if getattr(request.user, 'role_obj', None) else request.user.role
            allowed_by_role_name = current_role_name in allowed_roles

            if not (allowed_by_role_name or request.user.is_superuser):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'access_denied': True,
                        'message': f'Access denied. Required role: {", ".join(allowed_roles)}. Your role: {current_role_name}'
                    }, status=403)
                
                messages.error(request, f"Access Denied: You do not have the required role ({', '.join(allowed_roles)}) to perform this action.")
                return redirect(reverse('dashboard'))
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


## Role and Permission-based access control decorator
def permission_required(perm_or_perms):
    """
    Permission-based access control decorator.
    Checks if user's Role has the specific permission.
    Usage: @permission_required('projects.delete_projects')
           or @permission_required(['users.add_department', 'users.view_department'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Authentication required'
                    }, status=401)
                return redirect(reverse('login_page'))

            # Superuser always passes
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Check permission via Role object
            if isinstance(perm_or_perms, (list, tuple)):
                if any(request.user.has_perm(p) for p in perm_or_perms):
                    return view_func(request, *args, **kwargs)
            else:
                if request.user.has_perm(perm_or_perms):
                    return view_func(request, *args, **kwargs)

            # Access denied
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'access_denied': True,
                    'message': f'Access denied. Required permission(s): {perm_or_perms}'
                }, status=403)

            messages.error(request, f"Access Denied: You do not have the required permissions ({perm_or_perms}) to perform this action.")
            return redirect(reverse('dashboard'))

        return wrapped_view
    return decorator