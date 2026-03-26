import os
import django
import json
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pms_system.settings")
django.setup()

client = Client()

# Create a test user or find one
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.filter(is_superuser=True).first()
if not user:
    user = User.objects.create_superuser('admin@example.com', 'adminpass')
    email = 'admin@example.com'
else:
    user.set_password('adminpass')
    user.save()
    email = user.email

# Test Login
response = client.post('/api/auth/login/', json.dumps({
    'email': email,
    'password': 'adminpass'
}), content_type='application/json')

print("Login Status:", response.status_code)
if response.status_code == 200:
    data = response.json()
    access_token = data.get('access')
    refresh_token = data.get('refresh')
    print("Tokens received!")
else:
    print("Login Failed:", response.content)
    exit(1)

# Test Refresh
refresh_response = client.post('/api/auth/refresh/', json.dumps({
    'refresh': refresh_token
}), content_type='application/json')
print("Refresh Status:", refresh_response.status_code)

# Test Protected Endpoint without token
unauth_response = client.get('/api/dashboard/')
print("Unauth Dashboard Status:", unauth_response.status_code)

# Test Protected Endpoint with token
auth_response = client.get('/api/dashboard/', HTTP_AUTHORIZATION=f'Bearer {access_token}')
print("Auth Dashboard Status:", auth_response.status_code)
if auth_response.status_code == 200:
    print("Dashboard Auth SUCCESS")
