# ============================================================================
# STANDARD LIBRARY IMPORTS
# ============================================================================
import re
import json
import secrets
import string
from collections import defaultdict
from datetime import timedelta
# ============================================================================
# DJANGO CORE IMPORTS
# ============================================================================

from django.db import models
from django.db.models import Q, Avg
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.tokens import default_token_generator
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.urls import reverse
from users.models import UserPermissionOverride

# ============================================================================
# THIRD-PARTY APP IMPORTS (DRF SimpleJWT)
# ============================================================================

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
# ============================================================================
# PROJECT APP IMPORTS
# ============================================================================
from projects.models import Projects
from Tasks.models import Task
from notifications.models import Notification
from users.models import Role, User, UserProfile, Department, Designation, ActivityLog
from users.permissions import (
    can_add_task, can_manage_projects, can_manage_roles, can_manage_users,
    can_view_projects, can_view_task, can_view_user, can_start_task,
    can_resume_task, can_complete_task, dashboard_url_for, is_manager_like,
    has_any, get_task_queryset, get_projects_queryset
)
from .decorators import jwt_or_session_required, permission_required
from .forms import RoleForm, PermissionForm, UserRegisterForm, UserProfileForm
# ============================================================================
# USER MODEL INITIALIZATION
# ============================================================================
User = get_user_model()  

def login_view(request):
    return redirect("login_page")

def _active_users_queryset():
    return User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True)

def _contributor_user_ids():
    return [user.id for user in _active_users_queryset() if not is_manager_like(user)]

def _contributor_users_queryset():
    contributor_ids = _contributor_user_ids()
    return User.objects.filter(id__in=contributor_ids)


@csrf_exempt
def ajax_login(request):
    """JWT login endpoint for browser and API clients."""
    
    if request.method != "POST":
        return JsonResponse({"status": "error", "error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "error": "Invalid JSON"}, status=400)

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return JsonResponse({"status": "error", "error": "Email and password required"}, status=400)
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"status": "error", "error": "Email does not exist"}, status=401)
    
    if not user.is_active:
        return JsonResponse({"status": "error", "error": "Account is inactive"}, status=403)

   
    user = authenticate(request, username=email, password=password)

    if user is None:
        return JsonResponse({"status": "error", "error": "Incorrect password"}, status=401)

    if user.role_obj and user.role != user.role_obj.name:
        user.role = user.role_obj.name
        user.save(update_fields=['role'])

    role = user.role_obj.name if user.role_obj else (user.role or 'USER')
    redirect_url = dashboard_url_for(user)

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    response = JsonResponse({
        "status": "success",
        "role": role,
        "redirect_url": redirect_url,
        "username": user.username,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }
    })

    secure_cookie = not settings.DEBUG
    response.set_cookie('access_token', access_token, httponly=True, samesite='Lax', secure=secure_cookie)
    response.set_cookie('refresh_token', refresh_token, httponly=True, samesite='Lax', secure=secure_cookie)
    return response


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@jwt_or_session_required
def view_user_details(request, user_id):
    """User details - HTML shell only, data from API"""
    # Permission check (keep for HTML access)
    if request.user.id != user_id and not request.user.is_superuser and not request.user.has_perm('users.view_user'):
        messages.error(request, "Access Denied: You don't have permission to view other users' profiles.")
        return redirect('dashboard')
    
    return render(request, "users/view_user_details.html", {
        "user_id": user_id
    })


def login_page(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "GET":
            return JsonResponse({
                'success': True,
                'csrf_token': request.COOKIES.get('csrftoken', '')
            })
    
    return render(request, "auth/ajax_login.html")


@jwt_or_session_required
def dashboard(request):
    """Dashboard - data loaded via API"""
    
    return render(request, "dashboards/dashboard.html")



@jwt_or_session_required
def logout_view(request):
    refresh_token = None
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.headers.get('Accept') == 'application/json'
    )
    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
            refresh_token = body.get('refresh_token')
        except (json.JSONDecodeError, AttributeError):
            refresh_token = None

    if not refresh_token:
        refresh_token = request.COOKIES.get('refresh_token')

    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except (TokenError, Exception):
            pass

    if is_ajax:
        response = JsonResponse({
            'success': True,
            'message': 'Logged out successfully',
            'redirect_url': '/'
        })
    else:
        response = redirect('login_page')

    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    response.delete_cookie('user_role')
    response.delete_cookie('username')
    response.delete_cookie('user_id')
    return response



@jwt_or_session_required
@permission_required('users.change_user')
def edit_user_page(request, user_id):
    """Serve Edit User Page"""
    user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'employee_id': f"EMP-{user.id:04d}"})
    
    context = {
        "user": user,
        "profile": profile,
        "departments": Department.objects.all(),
        "designations": Designation.objects.all(),
        "roles": Role.objects.all().order_by('name'),
    }
    return render(request, "users/edit_user.html", context)

@jwt_or_session_required
@permission_required('users.change_user')
def get_user_details(request, user_id):
    """Return user details as JSON"""
    user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'employee_id': f"EMP-{user.id:04d}"})
    
    data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "username": user.username,
        "is_active": user.is_active,
        "role": user.role_obj.id if user.role_obj else None,
        "department": profile.department.id if profile.department else None,
        "designation": profile.designation.id if profile.designation else None,
        "employee_id": profile.employee_id,
        "phone": profile.phone,
        "emergency_contact": profile.emergency_contact,
        "aadhar_no": profile.aadhar_no,
        "pan_no": profile.pan_no,
        "date_of_joining": profile.date_of_joining.isoformat() if profile.date_of_joining else None,
        "ctc": profile.ctc,
        "salary_in_hand": profile.salary_in_hand,
        "bank_name": profile.bank_name,
        "account_no": profile.account_no,
        "ifsc": profile.ifsc,
        "address": profile.address,
        "profile_image": profile.profile_image.url if profile.profile_image else None,
    }
    return JsonResponse({"success": True, "data": data})


@jwt_or_session_required
@permission_required('users.change_user')
@csrf_exempt
def update_user(request, user_id):
    """Update user and profile details"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)
    
    user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'employee_id': f"EMP-{user.id:04d}"})
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    errors = {}
    
    email = request.POST.get("email")
    if not email:
        errors['email'] = ['Email is required']
    elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        errors['email'] = ['Please enter a valid email address']
    
    username = request.POST.get("username")
    if not username:
        errors['username'] = ['Username is required']
    elif len(username) < 3:
        errors['username'] = ['Username must be at least 3 characters long']
    
    role_obj_id = request.POST.get("role_obj")
    if not role_obj_id:
        errors['role_obj'] = ['Role is required']
    
    employee_id = request.POST.get("employee_id", "").strip()
    if not employee_id:
        errors['employee_id'] = ['Employee ID is required']
    elif len(employee_id) < 2:
        errors['employee_id'] = ['Employee ID must be at least 2 characters long']
    else:
        if UserProfile.objects.exclude(id=profile.id).filter(employee_id=employee_id).exists():
            errors['employee_id'] = ['Employee ID already exists. Please use a unique ID.']

    phone = request.POST.get("phone", "").strip()
    if phone and not re.match(r'^[6-9]\d{9}$', phone):
        errors['phone'] = ['Phone number must be 10 digits and start with 6, 7, 8, or 9']
    
    emergency_contact = request.POST.get("emergency_contact", "").strip()
    if emergency_contact and not re.match(r'^[6-9]\d{9}$', emergency_contact):
        errors['emergency_contact'] = ['Emergency contact must be 10 digits and start with 6, 7, 8, or 9']

    aadhar_no = request.POST.get("aadhar_no", "").strip()
    if aadhar_no and not re.match(r'^\d{12}$', aadhar_no):
        errors['aadhar_no'] = ['Aadhar number must be exactly 12 digits']
    
    ctc = request.POST.get("ctc", "").strip()
    if ctc:
        try:
            if float(ctc) < 0: errors['ctc'] = ['CTC cannot be negative']
        except ValueError: errors['ctc'] = ['Invalid number for CTC']
        
    salary_in_hand = request.POST.get("salary_in_hand", "").strip()
    if salary_in_hand:
        try:
            if float(salary_in_hand) < 0: errors['salary_in_hand'] = ['Salary cannot be negative']
        except ValueError: errors['salary_in_hand'] = ['Invalid number for salary']

    selected_role = None
    if role_obj_id:
        try:
            selected_role = Role.objects.get(id=role_obj_id)
        except Role.DoesNotExist:
            errors['role_obj'] = ['Invalid role selected']

    if errors:
        if is_ajax:
            response = JsonResponse({'success': False, 'errors': errors}, status=400)
        else:
            for field, err_list in errors.items():
                for err in err_list: messages.error(request, f"{field}: {err}")
            response = redirect("edit_user_page", user_id=user.id)
        response['Vary'] = 'X-Requested-With'
        return response

    user.email = email
    user.username = username
    user.first_name = request.POST.get("first_name", "")
    user.last_name = request.POST.get("last_name", "")
    user.role_obj = selected_role
    user.role = selected_role.name if selected_role else user.role
    user.is_active = (request.POST.get("is_active") == "True")
    user.save()

    profile.department_id = request.POST.get("department") or None
    profile.designation_id = request.POST.get("designation") or None
    profile.employee_id = employee_id or None
    profile.phone = phone or None
    profile.emergency_contact = emergency_contact or None
    profile.aadhar_no = aadhar_no or None
    profile.pan_no = request.POST.get("pan_no", "").upper() or None
    profile.ifsc = request.POST.get("ifsc", "").upper() or None
    profile.bank_name = request.POST.get("bank_name") or None
    profile.account_no = request.POST.get("account_no") or None
    profile.address = request.POST.get("address", "").strip() or None
    profile.ctc = ctc or None
    profile.salary_in_hand = salary_in_hand or None
    profile.date_of_joining = request.POST.get("date_of_joining") or None

    if request.FILES.get('profile_image'):
        image_file = request.FILES['profile_image']
        if image_file.size <= 5 * 1024 * 1024 and image_file.content_type.startswith('image/'):
            profile.profile_image = image_file

    profile.save()

    if is_ajax:
        response = JsonResponse({'success': True, 'message': f'User "{user.username}" updated successfully!', 'user_id': user.id})
    else:
        messages.success(request, "User updated successfully")
        response = redirect("admin_view_users")
    
    response['Vary'] = 'X-Requested-With'
    return response


def _get_permission_groups():
    permission_groups = defaultdict(list)
    permissions = Permission.objects.select_related('content_type').filter(
        content_type__app_label__in=['users', 'projects', 'Tasks', 'tasks', 'notifications']
    ).order_by('content_type__app_label', 'codename')

    for permission in permissions:
        permission_groups[permission.content_type.app_label].append(permission)

    return dict(permission_groups)


@jwt_or_session_required
@permission_required(['users.view_role', 'users.add_role', 'users.change_role'])
def role_list(request):
    roles = Role.objects.prefetch_related('permissions').all().order_by('name')
    return render(request, 'roles/role_list.html', {'roles': roles})


@jwt_or_session_required
@permission_required('users.add_role')
@csrf_exempt
def role_create(request):
    if request.method == 'POST':
        form = RoleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Role created successfully.')
            return redirect('role_list')
    else:
        form = RoleForm()

    selected_permission_ids = set(request.POST.getlist('permissions')) if request.method == 'POST' else set()
    context = {
        'form': form,
        'form_title': 'Create Role',
        'submit_label': 'Create Role',
        'permission_groups': _get_permission_groups(),
        'selected_permission_ids': selected_permission_ids,
    }
    return render(request, 'roles/role_form.html', context)


@jwt_or_session_required
@permission_required('users.change_role')
@csrf_exempt
def role_edit(request, role_id):
    role = get_object_or_404(Role, id=role_id)

    if request.method == 'POST':
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            form.save()
            messages.success(request, f'Role "{role.name}" updated successfully.')
            return redirect('role_list')
    else:
        form = RoleForm(instance=role)

    if request.method == 'POST':
        selected_permission_ids = set(request.POST.getlist('permissions'))
    else:
        selected_permission_ids = set(str(pid) for pid in role.permissions.values_list('id', flat=True))

    context = {
        'form': form,
        'role': role,
        'form_title': f'Edit Role: {role.name}',
        'submit_label': 'Update Role',
        'permission_groups': _get_permission_groups(),
        'selected_permission_ids': selected_permission_ids,
    }
    return render(request, 'roles/role_form.html', context)


@jwt_or_session_required
@permission_required('users.delete_role')
@csrf_exempt
def role_delete(request, role_id):
    role = get_object_or_404(Role, id=role_id)

    if role.users.filter(is_superuser=True).exists():
        messages.error(request, 'This role is assigned to one or more superuser accounts and cannot be deleted.')
        return redirect('role_list')

    if request.method == 'POST':
        fallback_role = Role.objects.exclude(id=role.id).order_by('name').first()
        if not fallback_role:
            messages.error(request, 'Create at least one other role before deleting this role.')
            return redirect('role_list')

        affected_users = User.objects.filter(role_obj=role)
        for user in affected_users:
            user.role_obj = fallback_role
            user.role = fallback_role.name
            user.save(update_fields=['role_obj', 'role'])

        role_name = role.name
        role.delete()
        messages.success(request, f'Role "{role_name}" deleted successfully.')

    return redirect('role_list')


@jwt_or_session_required
@permission_required(['users.view_user', 'users.add_user', 'users.change_user', 'users.delete_user'])
def admin_view_users(request):
    """Admin view users - HTML shell only, data from API"""

    return render(request, "users/admin_view_users.html")


@jwt_or_session_required
@permission_required(['users.view_user', 'Tasks.add_task'])
def teamlead_view_users(request):
    """Team lead view users - HTML shell only, data from API"""
    
    return render(request, 'users/teamlead_view_users.html')

from django.utils.http import urlsafe_base64_decode
@csrf_exempt
def activate_user(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if request.method == 'POST':
                password = request.POST.get('password')
                confirm_password = request.POST.get('confirm_password')
                
                if not password or not confirm_password:
                    return JsonResponse({
                        'success': False,
                        'message': 'Please enter a password'
                    }, status=400)
                
                if password != confirm_password:
                    return JsonResponse({
                        'success': False,
                        'message': 'Passwords do not match'
                    }, status=400)
                
                if len(password) < 8:
                    return JsonResponse({
                        'success': False,
                        'message': 'Password must be at least 8 characters long'
                    }, status=400)
                
                try:
                    user.set_password(password)
                    user.is_active = True
                    user.save()
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Account activated successfully! Redirecting to login...'
                    })
                except Exception as e:
                    return JsonResponse({
                        'success': False,
                        'message': f'Error activating account: {str(e)}'
                    }, status=500)
            
            return JsonResponse({
                'success': False,
                'message': 'Invalid request method'
            }, status=400)
        
        if request.method == 'POST':
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            
            if password and password == confirm_password:
                if len(password) >= 8:
                    user.set_password(password)
                    user.is_active = True
                    user.save()
                    messages.success(request, 'Account activated successfully! You can now login.')
                    return redirect('login_page')
                else:
                    messages.error(request, 'Password must be at least 8 characters long')
            else:
                messages.error(request, 'Passwords do not match')
            
            return render(request, 'auth/set_password.html', {'user': user})
        
        return render(request, 'auth/set_password.html', {'user': user})
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Activation link is invalid or has expired!'
            }, status=400)
        
        messages.error(request, 'Activation link is invalid or has expired!')
        return redirect('login_page')
    

@jwt_or_session_required
@csrf_exempt
@permission_required('users.add_user')
def create_user(request):

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "POST":
            user_form = UserRegisterForm(request.POST)
            profile_form = UserProfileForm(request.POST)

            errors = {}
            
           
            employee_id = request.POST.get('employee_id', '').strip()
            if not employee_id:
                errors['employee_id'] = ['Employee ID is required.']
            elif not employee_id.isdigit():
                errors['employee_id'] = ['Employee ID must contain only numbers (no alphabetic characters).']
            elif UserProfile.objects.filter(employee_id=employee_id).exists():
                errors['employee_id'] = ['Employee ID already exists. Please use a unique ID.']
            
      
            phone = request.POST.get('phone', '').strip()
            if phone:
                if not re.match(r'^[6-9]\d{9}$', phone):
                    errors['phone'] = ['Phone number must be 10 digits and start with 6, 7, 8, or 9']
            
    
            email = request.POST.get('email', '').strip()
            if not email:
                errors['email'] = ['Email is required']
            elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                errors['email'] = ['Please enter a valid email address']
            
    
            username = request.POST.get('username', '').strip()
            if not username:
                errors['username'] = ['Username is required']
            elif len(username) < 3:
                errors['username'] = ['Username must be at least 3 characters long']
            
           
            role_id = request.POST.get('role')
            if not role_id:
                errors['role'] = ['Role is required']
            
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            if not first_name:
                errors['first_name'] = ['First name is required']
            if not last_name:
                errors['last_name'] = ['Last name is required']
            
            department_id = request.POST.get('department')
            if not department_id:
                errors['department'] = ['Department is required']
            
            designation_id = request.POST.get('designation')
            if not designation_id:
                errors['designation'] = ['Designation is required']
            
            if not user_form.is_valid():
                for field, error_list in user_form.errors.items():
                    errors[field] = error_list
            
            if not profile_form.is_valid():
                for field, error_list in profile_form.errors.items():
                    errors[field] = error_list
            
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)
            
            def generate_random_password(length=12):
                alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                password = ''.join(secrets.choice(alphabet) for i in range(length))
                return password
            
            random_password = generate_random_password()
            
            user = user_form.save(commit=False)
            user.set_password(random_password)
            user.is_active = True
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.username = username
            
            if role_id:
                try:
                    role_obj = Role.objects.get(id=role_id)
                    user.role_obj = role_obj
                    user.role = role_obj.name
                except Role.DoesNotExist:
                    pass
            
            try:
                subject = 'Your Account Has Been Created - Login Credentials'
                html_message = render_to_string('emails/activation_email.html', {
                    'user': user,
                    'password': random_password,
                    'site_name': 'PMS',
                    'login_url': request.build_absolute_uri(reverse('login_page'))
                })
                plain_message = strip_tags(html_message)
                
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
            except Exception as email_err:
                return JsonResponse({
                    'success': False,
                    'errors': {
                        'email_error': [f'Failed to send email: {str(email_err)}. User was not created.']
                    }
                }, status=400)
            
            try:
                user.save()
                
                profile = user.profile
                profile.employee_id = employee_id.strip()
                profile.phone = phone or None
                profile.department_id = department_id
                profile.designation_id = designation_id
                profile.date_of_joining = request.POST.get('date_of_joining') or None
                profile.save()

                return JsonResponse({
                    'success': True,
                    'message': f"User '{user.username}' created successfully! Login credentials sent to {user.email}",
                    'redirect_url': request.POST.get('redirect_url', 'dashboards/admin_dashboard/'),
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                        'role': user.role,
                        'employee_id': profile.employee_id,
                        'department': profile.department.name if profile.department else None,
                        'designation': profile.designation.name if profile.designation else None,
                    }
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'errors': {
                        'system_error': [f"Error creating user: {str(e)}"]
                    }
                }, status=500)
    
        elif request.method == "GET":
            roles = Role.objects.all().values('id', 'name')
            departments = Department.objects.all().values('id', 'name')
            designations = Designation.objects.all().values('id', 'name')
            
            user_fields = {
                'first_name': {'label': 'First Name', 'required': True, 'type': 'text', 'minlength': 2},
                'last_name': {'label': 'Last Name', 'required': True, 'type': 'text', 'minlength': 2},
                'email': {'label': 'Email', 'required': True, 'type': 'email', 'pattern': '[^@]+@[^@]+\\.[a-zA-Z]{2,}'},
                'username': {'label': 'Username', 'required': True, 'type': 'text', 'minlength': 3, 'pattern': '[A-Za-z0-9_]{3,}'},
                'role': {'label': 'Role', 'required': True, 'type': 'select', 'options': list(roles)},
            }
            
            profile_fields = {
                'employee_id': {
                    'label': 'Employee ID', 
                    'required': True, 
                    'type': 'text', 
                    'minlength': 2,
                    'pattern': '[0-9]+',
                    'help_text': 'Only numbers are allowed for Employee ID'
                },
                'phone': {'label': 'Phone', 'required': False, 'type': 'tel', 'pattern': '[6-9][0-9]{9}', 'maxlength': 10, 'help_text': '10 digits, starts with 6/7/8/9'},
                'department': {'label': 'Department', 'required': True, 'type': 'select', 'options': list(departments)},
                'designation': {'label': 'Designation', 'required': True, 'type': 'select', 'options': list(designations)},
                'date_of_joining': {'label': 'Date of Joining', 'required': False, 'type': 'date'},
            }
            
            return JsonResponse({
                'success': True,
                'user_fields': user_fields,
                'profile_fields': profile_fields,
            })
    
    return render(request, "users/create_user.html")


@jwt_or_session_required
@permission_required('users.delete_user')
def delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)

    if user_to_delete == request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'You cannot delete your own account.'
            }, status=400)
        messages.error(request, "You cannot delete your own account.")
        return redirect("admin_dashboard")

    user_name = user_to_delete.username
    
    if request.method == "POST":
        user_to_delete.delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'User "{user_name}" deleted successfully!',
                'user_id': user_id
            })
        
        messages.success(request, f'User "{user_name}" deleted successfully!')
        return redirect("admin_dashboard")
    
    return redirect("admin_dashboard")


@jwt_or_session_required
@permission_required(['users.view_department', 'users.add_department', 'users.change_department', 'users.delete_department'])
def departments(request):
    """Departments list - HTML shell only, data from API"""
    return render(request, "department/department_list.html")


@jwt_or_session_required
@permission_required('users.add_department')
@csrf_exempt
def create_department(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            department = Department.objects.create(name=name)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    "success": True,
                    "message": f"Department '{name}' created successfully!",
                    "department": {
                        "id": department.id,
                        "name": department.name
                    }
                })
            
            messages.success(request, "Department created successfully!")
            return redirect("departments")
    
    return render(request, "department/department_list.html", {"action": "Create"})


@jwt_or_session_required
@permission_required(['users.view_department', 'users.add_department', 'users.change_department', 'users.delete_department'])
def department_detail(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    return render(request, "department/department_detail.html", {
        "department": department
    })


@jwt_or_session_required
@permission_required(['users.view_department'])
def department_members_api(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    users_in_dept = User.objects.filter(profile__department=department)
    
    users_list = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "designation": user.profile.designation.name if user.profile.designation else "N/A"
        }
        for user in users_in_dept
    ]
    return JsonResponse({
        "success": True,
        "department": department.name,
        "users": users_list
    })


@jwt_or_session_required
@permission_required('users.delete_department')
@csrf_exempt
def delete_department(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    dept_name = department.name
    
    if request.method == "POST":
        department.delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "message": f"Department '{dept_name}' deleted successfully!",
                "dept_id": dept_id
            })
        
        messages.success(request, "Department deleted successfully!")
        return redirect("departments")
    
    return redirect("departments")


@jwt_or_session_required
@permission_required(['users.view_designation', 'users.add_designation', 'users.change_designation', 'users.delete_designation'])
def designations(request):
    """Designations list - HTML shell only, data from API"""
    return render(request, "designation/designation_list.html")



@jwt_or_session_required
@permission_required('users.add_designation')
@csrf_exempt
def create_designation(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            designation = Designation.objects.create(name=name)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    "success": True,
                    "message": f"Designation '{name}' created successfully!",
                    "designation": {
                        "id": designation.id,
                        "name": designation.name
                    }
                })
            
            messages.success(request, "Designation created successfully!")
            return redirect("designations")
    
    return render(request, "designation/designation_form.html", {"action": "Create"})


@jwt_or_session_required
@permission_required(['users.view_designation', 'users.add_designation', 'users.change_designation', 'users.delete_designation'])
def designation_detail(request, desig_id):
    designation = get_object_or_404(Designation, id=desig_id)
    return render(request, "designation/designation_detail.html", {
        "designation": designation
    })


@jwt_or_session_required
@permission_required(['users.view_designation'])
def designation_members_api(request, desig_id):
    designation = get_object_or_404(Designation, id=desig_id)
    users_in_desig = User.objects.filter(profile__designation=designation)
    
    users_list = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role or "N/A",
            "role_display": user.role or "N/A",
            "department": user.profile.department.name if hasattr(user, 'profile') and user.profile.department else "N/A",
            "full_name": user.get_full_name() or user.username
        }
        for user in users_in_desig
    ]
    return JsonResponse({
        "success": True,
        "designation": designation.name,
        "designation_id": designation.id,
        "users": users_list,
        "total_users": len(users_list)
    })


@jwt_or_session_required
@permission_required('users.delete_designation')
@csrf_exempt
def delete_designation(request, desig_id):
    desig = get_object_or_404(Designation, id=desig_id)
    desig_name = desig.name
    
    if request.method == "POST":
        desig.delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "message": f"Designation '{desig_name}' deleted successfully!",
                "desig_id": desig_id
            })
        
        messages.success(request, "Designation deleted successfully!")
        return redirect("designations")
    
    return redirect("designations")



@jwt_or_session_required
@permission_required(['Tasks.view_task', 'users.view_user'])
def user_analytics(request):
    """User analytics - HTML shell only, data from API"""
    return render(request, 'users/user_analytics.html')


def home(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        token = None
        
        auth_cookie = request.COOKIES.get('access_token')
        if auth_cookie:
            token = auth_cookie
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        user_data = None
        if token:
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                user = User.objects.get(id=user_id)
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'full_name': user.get_full_name() or user.username
                }
            except (TokenError, User.DoesNotExist):
                pass
        
        return JsonResponse({
            'success': True,
            'is_authenticated': user_data is not None,
            'user': user_data
        })
    return render(request, "home.html")


@csrf_exempt
@require_http_methods(["POST"])
def check_email_exists(request):
    """Check if email is registered in the system - Public endpoint"""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({'exists': False, 'error': 'Email is required'}, status=400)
        
        user_exists = User.objects.filter(email=email).exists()
        
        return JsonResponse({
            'exists': user_exists,
            'message': 'Email found' if user_exists else 'No account found with this email'
        })
        
    except Exception as e:
        return JsonResponse({'exists': False, 'error': str(e)}, status=500)


@jwt_or_session_required
def my_profile(request):
    """View for logged-in user to see their own profile and upload image"""
    user = request.user
    profile = user.profile
    
    if request.method == "POST" and request.FILES.get('profile_image'):
        profile.profile_image = request.FILES['profile_image']
        profile.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Profile picture updated successfully!',
                'image_url': profile.profile_image.url if profile.profile_image else None
            })
    
    return render(request, 'users/my_profile.html', {
        'user': user,
        'profile': profile
    })


@jwt_or_session_required
@permission_required('projects.view_projects')
def trash_view(request):
    """View all soft-deleted projects and tasks"""
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    deleted_projects = Projects.objects.filter(
        is_deleted=True,
        created_by=request.user
    ).order_by('-deleted_at')
    
    deleted_tasks = Task.objects.filter(
        is_deleted=True
    ).filter(
        Q(created_by=request.user) | Q(assigned_by=request.user)
    ).distinct().order_by('-deleted_at')
    
    if is_ajax:
        projects_data = []
        for project in deleted_projects:
            projects_data.append({
                'id': project.id,
                'name': project.name,
                'type': 'project',
                'deleted_at': project.deleted_at.strftime('%Y-%m-%d %H:%M:%S') if project.deleted_at else None,
                'restore_url': f'/trash/restore/project/{project.id}/',
                'permanent_delete_url': f'/trash/permanent/project/{project.id}/'
            })
        
        tasks_data = []
        for task in deleted_tasks:
            tasks_data.append({
                'id': task.id,
                'name': task.name,
                'type': 'task',
                'project_name': task.project.name,
                'deleted_at': task.deleted_at.strftime('%Y-%m-%d %H:%M:%S') if task.deleted_at else None,
                'restore_url': f'/trash/restore/task/{task.id}/',
                'permanent_delete_url': f'/trash/permanent/task/{task.id}/'
            })
        
        return JsonResponse({
            'success': True,
            'projects': projects_data,
            'tasks': tasks_data,
            'total_projects': deleted_projects.count(),
            'total_tasks': deleted_tasks.count()
        })
    
    return render(request, 'trash/trash.html', {
        'deleted_projects': deleted_projects,
        'deleted_tasks': deleted_tasks
    })

@jwt_or_session_required
@csrf_exempt
def restore_item(request, item_type, item_id):
    """Restore a soft-deleted project or task"""
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if item_type == 'project':
        item = get_object_or_404(Projects, id=item_id)
        
        if item.created_by != request.user:
            error_msg = "Only the project creator can restore this project"
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=403)
            messages.error(request, error_msg)
            return redirect('trash_view')
        
        if not item.is_deleted:
            error_msg = "Project is not deleted"
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('trash_view')
        
        item.is_deleted = False
        item.deleted_at = None
        item.save()
        
        from users.models import ActivityLog
        ActivityLog.objects.create(
            user=request.user,
            action='restored',
            entity_type='project',
            entity_id=item.id,
            entity_name=item.name
        )
        
        message = f'Project "{item.name}" restored successfully!'
        
    elif item_type == 'task':
        item = get_object_or_404(Task, id=item_id)
        is_task_owner = item.assigned_by.filter(id=request.user.id).exists()
        is_project_creator = item.project.created_by == request.user
        
        if not (is_task_owner or is_project_creator):
            error_msg = "Only task owner or project creator can restore this task"
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=403)
            messages.error(request, error_msg)
            return redirect('trash_view')
        
        if not item.is_deleted:
            error_msg = "Task is not deleted"
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('trash_view')
        
        item.is_deleted = False
        item.deleted_at = None
        item.save()
        
        from users.models import ActivityLog
        ActivityLog.objects.create(
            user=request.user,
            action='restored',
            entity_type='task',
            entity_id=item.id,
            entity_name=item.name
        )
        
        message = f'Task "{item.name}" restored successfully!'
        
    else:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Invalid item type'}, status=400)
        messages.error(request, 'Invalid item type')
        return redirect('trash_view')
    
    if is_ajax:
        return JsonResponse({'success': True, 'message': message})
    
    messages.success(request, message)
    return redirect('trash_view')


@jwt_or_session_required
@csrf_exempt
def permanent_delete_item(request, item_type, item_id):
    """Permanently delete an item from trash (hard delete)"""
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if item_type == 'project':
        item = get_object_or_404(Projects, id=item_id)
        
        if item.created_by != request.user:
            error_msg = "Only the project creator can permanently delete this project"
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=403)
            messages.error(request, error_msg)
            return redirect('trash_view')
        
        if not item.is_deleted:
            error_msg = "Project is not in trash"
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('trash_view')
        
        name = item.name
        item.delete()  
        
        message = f'Project "{name}" permanently deleted!'
        
    elif item_type == 'task':
        item = get_object_or_404(Task, id=item_id)
        
        is_task_owner = item.assigned_by.filter(id=request.user.id).exists()
        is_project_creator = item.project.created_by == request.user
        
        if not (is_task_owner or is_project_creator):
            error_msg = "Only task owner or project creator can permanently delete this task"
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=403)
            messages.error(request, error_msg)
            return redirect('trash_view')
        
        if not item.is_deleted:
            error_msg = "Task is not in trash"
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('trash_view')
        
        name = item.name
        item.delete()  
        
        message = f'Task "{name}" permanently deleted!'
        
    else:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Invalid item type'}, status=400)
        messages.error(request, 'Invalid item type')
        return redirect('trash_view')
    
    if is_ajax:
        return JsonResponse({'success': True, 'message': message})
    
    messages.success(request, message)
    return redirect('trash_view')


@jwt_or_session_required
def activity_log_view(request, project_id=None):
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if project_id:
        project = get_object_or_404(Projects, id=project_id)
        
        if project.created_by != request.user:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Only project creator can view activity log'}, status=403)
            messages.error(request, 'Only project creator can view activity log')
            return redirect('view_project_detail', project_id=project_id)
        
      
        from users.models import ActivityLog
        
        activities = ActivityLog.objects.filter(
            entity_type__in=['project', 'task'],
            entity_id=project_id
        ).filter(
           
            models.Q(entity_type='project', entity_id=project_id) |
            models.Q(entity_type='task', entity_id__in=project.task_set.values_list('id', flat=True))
        ).order_by('-timestamp')
        
        page_size = int(request.GET.get('page_size', 20))
        page = int(request.GET.get('page', 1))
        
        from django.core.paginator import Paginator
        paginator = Paginator(activities, page_size)
        activities_page = paginator.get_page(page)
        
        if is_ajax:
            activities_data = []
            for activity in activities_page:
                activities_data.append({
                    'id': activity.id,
                    'user': activity.user.username if activity.user else 'System',
                    'action': activity.get_action_display(),
                    'entity_type': activity.get_entity_type_display(),
                    'entity_name': activity.entity_name,
                    'timestamp': activity.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'old_value': activity.old_value,
                    'new_value': activity.new_value
                })
            
            return JsonResponse({
                'success': True,
                'activities': activities_data,
                'total': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': activities_page.number,
                'has_previous': activities_page.has_previous(),
                'has_next': activities_page.has_next(),
                'project_name': project.name
            })
        
        return render(request, 'logs/activity_log.html', {
            'project': project,
            'activities': activities_page,
            'paginator': paginator,
            'page_obj': activities_page
        })
    
    else:
        if not request.user.is_superuser:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
            messages.error(request, 'Access denied')
            return redirect('dashboard')
        
        from users.models import ActivityLog
        activities = ActivityLog.objects.all().order_by('-timestamp')
        
        page_size = int(request.GET.get('page_size', 50))
        page = int(request.GET.get('page', 1))
        
        from django.core.paginator import Paginator
        paginator = Paginator(activities, page_size)
        activities_page = paginator.get_page(page)
        
        if is_ajax:
            activities_data = []
            for activity in activities_page:
                activities_data.append({
                    'id': activity.id,
                    'user': activity.user.username if activity.user else 'System',
                    'action': activity.get_action_display(),
                    'entity_type': activity.get_entity_type_display(),
                    'entity_name': activity.entity_name,
                    'timestamp': activity.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return JsonResponse({
                'success': True,
                'activities': activities_data,
                'total': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': activities_page.number,
                'has_previous': activities_page.has_previous(),
                'has_next': activities_page.has_next()
            })
        
        return render(request, 'logs/activity_log_all.html', {
            'activities': activities_page,
            'paginator': paginator,
            'page_obj': activities_page
        })
    

# ============================================================================
# PERMISSION OVERRIDES MANAGEMENT
# ============================================================================

@jwt_or_session_required
def permission_overrides(request):
    """Render the permission overrides management page"""
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        messages.error(request, "You don't have permission to manage permission overrides.")
        return redirect('dashboard')
    return render(request, 'permissions/permission_overrides.html')


@jwt_or_session_required
def get_permission_overrides(request):
    """API endpoint to get all permission overrides"""
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    overrides = UserPermissionOverride.objects.select_related('user', 'granted_by').all().order_by('-granted_at')
    
    data = []
    for override in overrides:
        data.append({
            'id': override.id,
            'user_id': override.user.id,
            'user_name': override.user.get_full_name() or override.user.username,
            'user_email': override.user.email,
            'permission': override.permission,
            'is_granted': override.is_granted,
            'granted_by_name': override.granted_by.username if override.granted_by else 'System',
            'granted_at': override.granted_at.strftime('%Y-%m-%d %H:%M:%S'),
            'reason': override.reason or '',
        })
    
    return JsonResponse({
        'success': True,
        'overrides': data,
        'total': len(data)
    })


@jwt_or_session_required
@csrf_exempt
def create_permission_override(request):
    """API endpoint to create a new permission override"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        permission = data.get('permission', '').strip()
        is_granted = data.get('is_granted', True)
        reason = data.get('reason', '').strip()
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'User is required'}, status=400)
        
        if not permission:
            return JsonResponse({'success': False, 'error': 'Permission is required'}, status=400)
        
        user = get_object_or_404(User, id=user_id)
        
        # Check if override already exists
        existing = UserPermissionOverride.objects.filter(user=user, permission=permission).first()
        if existing:
            return JsonResponse({
                'success': False, 
                'error': f'Override for "{permission}" already exists for this user. Please delete it first if you want to change it.'
            }, status=400)
        
        override = UserPermissionOverride.objects.create(
            user=user,
            permission=permission,
            is_granted=is_granted,
            granted_by=request.user,
            reason=reason
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{"GRANT" if is_granted else "DENY"} override created for "{permission}"',
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@jwt_or_session_required
@csrf_exempt
def delete_permission_override(request, override_id):
    """API endpoint to delete a permission override"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    override = get_object_or_404(UserPermissionOverride, id=override_id)
    permission_name = override.permission
    user_name = override.user.get_full_name() or override.user.username
    override.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Override for "{permission_name}" removed from {user_name}'
    })



@jwt_or_session_required
@csrf_exempt
def sync_permission_overrides(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        grant_permissions = data.get('grant_permissions', [])
        deny_permissions = data.get('deny_permissions', [])
        
        user = get_object_or_404(User, id=user_id)
        
        # Delete all existing overrides for this user
        UserPermissionOverride.objects.filter(user=user).delete()
        
        # Create GRANT overrides
        for permission in grant_permissions:
            UserPermissionOverride.objects.create(
                user=user,
                permission=permission,
                is_granted=True,
                granted_by=request.user,
                reason='GRANT override via UI'
            )
        
        # Create DENY overrides
        for permission in deny_permissions:
            UserPermissionOverride.objects.create(
                user=user,
                permission=permission,
                is_granted=False,
                granted_by=request.user,
                reason='DENY override via UI'
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Saved {len(grant_permissions)} GRANT and {len(deny_permissions)} DENY overrides'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@jwt_or_session_required
def get_all_permissions(request):
    """Get all available permissions grouped by module"""
    from django.contrib.auth.models import Permission
    
    permissions = Permission.objects.select_related('content_type').filter(
        content_type__app_label__in=['users', 'projects', 'Tasks', 'notifications']
    ).order_by('content_type__app_label', 'codename')
    
    data = []
    for perm in permissions:
        data.append({
            'id': perm.id,
            'name': perm.name,
            'codename': perm.codename,
            'app_label': perm.content_type.app_label,
            'module': perm.content_type.app_label.title()
        })
    
    return JsonResponse({'success': True, 'permissions': data})


@jwt_or_session_required
@permission_required(['auth.view_permission', 'auth.add_permission'])
def permission_list(request):
    permissions = Permission.objects.select_related('content_type').all().order_by('content_type__app_label', 'codename')
    return render(request, 'permissions/permission_list.html', {'permissions': permissions})


@jwt_or_session_required
@permission_required('auth.add_permission')
def permission_create(request):
    if request.method == 'POST':
        form = PermissionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Permission created successfully.')
            return redirect('permission_list')
    else:
        form = PermissionForm()
    return render(request, 'permissions/permission_form.html', {'form': form})


@jwt_or_session_required
@permission_required('auth.delete_permission')
def permission_delete(request, perm_id):
    perm = get_object_or_404(Permission, id=perm_id)
    if request.method == 'POST':
        perm.delete()
        messages.success(request, 'Permission deleted successfully.')
        return redirect('permission_list')
    return render(request, 'permissions/permission_confirm_delete.html', {'permission': perm})
