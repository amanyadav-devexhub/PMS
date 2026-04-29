from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
import urllib.parse

class JWTAuthMiddleware:
    """
    Custom middleware to authenticate WebSockets using JWT from cookies or headers.
    """
    def __init__(self, inner):
        self.inner = inner
        self.auth = JWTAuthentication()

    async def __call__(self, scope, receive, send):
        
        scope['user'] = AnonymousUser()
        
        
        token = None
        
       
        headers = dict(scope.get('headers', []))
        if b'cookie' in headers:
            cookies = headers[b'cookie'].decode('utf-8')
            parsed_cookies = {}
            for cookie in cookies.split(';'):
                if '=' in cookie:
                    key, value = cookie.strip().split('=', 1)
                    parsed_cookies[key] = value
            token = parsed_cookies.get('access_token')
            
      
        if not token and scope.get('query_string'):
            query_string = scope['query_string'].decode('utf-8')
            params = urllib.parse.parse_qs(query_string)
            token = params.get('token', [None])[0]

       
        if not token and b'authorization' in headers:
            auth_header = headers[b'authorization'].decode('utf-8')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1].strip()

        if token:
            user = await self.get_user_from_token(token)
            if user:
                scope['user'] = user

        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            validated_token = self.auth.get_validated_token(token)
            user = self.auth.get_user(validated_token)
            if user and user.is_active:
                return user
        except (InvalidToken, AuthenticationFailed, Exception):
            pass
        return None
