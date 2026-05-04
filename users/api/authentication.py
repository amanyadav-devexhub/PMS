from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication

class JWTCookieAuthentication(JWTAuthentication):
    
    def authenticate(self, request):
       
        cookie_name = getattr(settings, 'JWT_AUTH_COOKIE', 'access_token')
        raw_token = request.COOKIES.get(cookie_name)
        
        if raw_token is not None:
           
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token

        
        return super().authenticate(request)
