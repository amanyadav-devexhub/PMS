# users/decorators.py
from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt

User = get_user_model()

# def jwt_or_session_required(view_func):
#     """
#     Decorator that REQUIRES authentication via EITHER:
#     - JWT token (for Postman/mobile apps)
#     - Session cookie (for web browsers)
    
#     For API requests (X-Requested-With or Authorization header),
#     it MUST have a valid JWT token.
#     """
#     @wraps(view_func)
#     def wrapped_view(request, *args, **kwargs):
#         # Check if this is an API request
#         is_api_request = (
#             request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
#             request.headers.get('Authorization') is not None
#         )
        
#         # For API requests, JWT token is MANDATORY
#         if is_api_request:
#             auth_header = request.headers.get('Authorization')
            
#             if not auth_header:
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Authorization header required. Please provide JWT token.'
#                 }, status=401)
            
#             if not auth_header.startswith('Bearer '):
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Invalid Authorization header format. Use: Bearer <token>'
#                 }, status=401)
            
#             # Extract token
#             token = auth_header.split(' ')[1]
            
#             # Authenticate with JWT
#             auth = JWTAuthentication()
#             try:
#                 # Manually authenticate the token
#                 validated_token = auth.get_validated_token(token)
#                 user = auth.get_user(validated_token)
                
#                 if user is None or not user.is_active:
#                     return JsonResponse({
#                         'success': False,
#                         'error': 'Invalid or inactive user.'
#                     }, status=401)
                
#                 # Set the user on request
#                 request.user = user
                
#             except InvalidToken as e:
#                 return JsonResponse({
#                     'success': False,
#                     'error': f'Invalid token: {str(e)}'
#                 }, status=401)
#             except AuthenticationFailed as e:
#                 return JsonResponse({
#                     'success': False,
#                     'error': f'Authentication failed: {str(e)}'
#                 }, status=401)
#             except Exception as e:
#                 return JsonResponse({
#                     'success': False,
#                     'error': f'Token validation error: {str(e)}'
#                 }, status=401)
            
#             # JWT authentication successful, continue to view
#             return view_func(request, *args, **kwargs)
        
#         # For non-API requests (web browsers), use session authentication
#         if not request.user.is_authenticated:
#             # Redirect to login for web browsers
#             from django.shortcuts import redirect
#             from django.urls import reverse
#             return redirect(reverse('login_page'))
        
#         return view_func(request, *args, **kwargs)
    
#     return wrapped_view


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












# users/decorators.py - Add this new decorator

def jwt_required(view_func):
    """
    PURE JWT authentication - NO session fallback
    Extracts token from URL (for page loads) or Authorization header (for AJAX)
    """
    @wraps(view_func)
    @csrf_exempt
    def wrapped_view(request, *args, **kwargs):
        # Try to get token from URL first (for page loads)
        token = request.GET.get('token')
        
        # If not in URL, try Authorization header (for AJAX)
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        # If no token found, redirect to login
        if not token:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required. No token provided.'
                }, status=401)
            return redirect('/render_login/')
        
        # Validate JWT token
        auth = JWTAuthentication()
        try:
            validated_token = auth.get_validated_token(token)
            user = auth.get_user(validated_token)
            request.user = user
        except (InvalidToken, AuthenticationFailed) as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid token: {str(e)}'
                }, status=401)
            return redirect('/render_login/')
        
        return view_func(request, *args, **kwargs)
    
    return wrapped_view