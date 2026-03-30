from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication

class JWTCookieAuthentication(JWTAuthentication):
    """
    Custom DRF authentication class that looks for the JWT in the HTTP cookies 
    before falling back to the standard Authorization header.
    """
    def authenticate(self, request):
        # 1. Try to get token from cookies
        cookie_name = getattr(settings, 'JWT_AUTH_COOKIE', 'access_token')
        raw_token = request.COOKIES.get(cookie_name)
        
        if raw_token is not None:
            # Validate token like normal
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token

        # 2. Fall back to standard Authorization header
        return super().authenticate(request)
