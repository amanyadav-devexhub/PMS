from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed


class JWTAuthenticationMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        self.auth = JWTAuthentication()

    def __call__(self, request):
        request.user = AnonymousUser()

        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()

        if not token:
            token = request.COOKIES.get('access_token')

        if token:
            try:
                validated_token = self.auth.get_validated_token(token)
                user = self.auth.get_user(validated_token)
                if user and user.is_active:
                    request.user = user
            except (InvalidToken, AuthenticationFailed, Exception):
                request.user = AnonymousUser()

        return self.get_response(request)
