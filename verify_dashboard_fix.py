import json
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from users.views import ajax_login, dashboard
from users.decorators import jwt_required
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

def verify_fixes():
    # Setup superuser with empty role
    email = "admin@gmail.com"
    user = User.objects.get(email=email)
    user.role = ""
    user.save()
    
    factory = RequestFactory()
    
    print(f"--- Verifying Fixes for User: {user.email} (Superuser: {user.is_superuser}, Role: '{user.role}') ---")

    # 1. Verify ajax_login response returns JWT tokens and ADMIN role.
    data = {"email": email, "password": "admin"}
    request = factory.post('/ajax_login/', data=json.dumps(data), content_type='application/json')

    response = ajax_login(request)
    resp_data = json.loads(response.content)
    print(f"1. AJAX Login Role: {resp_data.get('role')}")
    assert resp_data.get('role') == 'ADMIN', "AJAX Login should return 'ADMIN' for superuser"
    assert resp_data.get('access_token'), "AJAX Login should return access token"
    assert resp_data.get('refresh_token'), "AJAX Login should return refresh token"

    # 2. Verify JWT-protected dashboard decorator accepts Bearer token.
    @jwt_required
    def protected_dashboard(req):
        return dashboard(req)

    access_token = str(RefreshToken.for_user(user).access_token)
    request = factory.get('/dashboard/', HTTP_AUTHORIZATION=f'Bearer {access_token}')
    response = protected_dashboard(request)
    print(f"2. Protected dashboard status: {response.status_code}")
    assert response.status_code in (200, 302), "JWT-protected dashboard should be accessible"

    print("\n[SUCCESS] JWT-only authentication checks passed.")

if __name__ == "__main__":
    verify_fixes()
