

# Create your views here.
## login & logout required libraries
import profile
from urllib import request
from django.db import models

from .decorators import allowed_roles, permission_required
from users.decorators import jwt_or_session_required
from django.contrib.auth import authenticate
from django.contrib.auth import logout
from collections import defaultdict
from django.utils.encoding import force_str

from .forms import RoleForm

## email related libraries
from django.core.mail import send_mail
from django.conf import settings

## Account activation tokens
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from datetime import timedelta
from django.db.models import Avg

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth import authenticate
from django.contrib import messages
from projects.models import Projects, ProjectResource
from projects.forms import ProjectResourceForm

## for notification logic
from notifications.models import Notification
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from users.models import Role, User
from users.permissions import (
    can_add_task,
    can_change_projects,
    can_change_task,
    can_delete_task,
    can_manage_all_tasks,
    can_manage_projects,
    can_manage_roles,
    can_manage_users,
    can_view_all_projects,
    can_view_all_tasks,
    can_view_projects,
    can_view_task,
    can_start_task,
    can_resume_task,
    can_complete_task,
    dashboard_url_for,
    is_manager_like,
    has_any,
)
from .forms import RoleForm, PermissionForm
from Tasks.models import Task

## Used for Session based login
def login_view(request):
    return redirect("login_page")


def _active_users_queryset():
    return User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True)


def _contributor_user_ids():
    return [user.id for user in _active_users_queryset() if not is_manager_like(user)]


def _contributor_users_queryset():
    contributor_ids = _contributor_user_ids()
    return User.objects.filter(id__in=contributor_ids)


from django.http import JsonResponse
import json

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.http import JsonResponse
from django.contrib.auth import authenticate,get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth.models import Permission
User = get_user_model()

## ajax login
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

    # Authenticate
    user = authenticate(request, username=email, password=password)

    if user is None:
        return JsonResponse({"status": "error", "error": "Incorrect password"}, status=401)

    # Keep legacy role text synced when a Role object exists.
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

    # Cookie support for browser page loads (JWT-only auth, no sessions).
    secure_cookie = not settings.DEBUG
    response.set_cookie('access_token', access_token, httponly=True, samesite='Lax', secure=secure_cookie)
    response.set_cookie('refresh_token', refresh_token, httponly=True, samesite='Lax', secure=secure_cookie)
    return response


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


## View Projects
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
@jwt_or_session_required
@permission_required('projects.view_projects')
def view_projects(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get("search", "").strip()
        page = request.GET.get("page", 1)
        page_size = request.GET.get("page_size", 10)
        
        if can_view_all_projects(request.user):
            projects = Projects.objects.all()
        else:
            projects = Projects.objects.filter(assigned_to=request.user)

        # Apply search filter
        if search_query:
            projects = projects.filter(
                Q(name__icontains=search_query) |
                Q(assigned_to__username__icontains=search_query) |
                Q(assigned_to__first_name__icontains=search_query) |
                Q(assigned_to__last_name__icontains=search_query) |
                Q(status__icontains=search_query)
            ).distinct()

        # Order projects
        projects = projects.order_by('-start_date')
        
        # Apply pagination
        paginator = Paginator(projects, page_size)
        try:
            projects_page = paginator.page(page)
        except PageNotAnInteger:
            projects_page = paginator.page(1)
        except EmptyPage:
            projects_page = paginator.page(paginator.num_pages)
        
        # Prepare data for JSON response
        projects_data = []
        for project in projects_page:
            # Get assigned users
            assigned_users = []
            for user in project.assigned_to.all():
                assigned_users.append({
                    'id': user.id,
                    'name': user.get_full_name() or user.username,
                    'email': user.email
                })
            
            # Get status badge class and text
            status_info = {
                'PENDING': {'class': 'bg-yellow-100 text-yellow-700', 'text': 'Pending'},
                'ONGOING': {'class': 'bg-blue-100 text-blue-700', 'text': 'Ongoing'},
                'COMPLETED': {'class': 'bg-green-100 text-green-700', 'text': 'Completed'}
            }
            status = status_info.get(project.status, {'class': 'bg-gray-100 text-gray-700', 'text': project.status})
            
            projects_data.append({
                'id': project.id,
                'name': project.name,
                'assigned_to': assigned_users,
                'assigned_to_display': ', '.join([u['name'] for u in assigned_users]) if assigned_users else 'Not assigned',
                'status': project.status,
                'status_display': status['text'],
                'status_class': status['class'],
                'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else None,
                'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else None,
                'view_url': f"/project/{project.id}/",
                'delete_url': f"/project/{{ project.id }}/delete/"
            })
        
        return JsonResponse({
            'success': True,
            'projects': projects_data,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': projects_page.number,
            'has_previous': projects_page.has_previous(),
            'has_next': projects_page.has_next(),
            'previous_page_number': projects_page.previous_page_number() if projects_page.has_previous() else None,
            'next_page_number': projects_page.next_page_number() if projects_page.has_next() else None,
            'page_size': int(page_size),
            'search_query': search_query
        })
    
    # Handle regular (non-AJAX) request
    search_query = request.GET.get("search", "")
    page = request.GET.get("page", 1)
    page_size = 10
    
    if can_view_all_projects(request.user):
        projects = Projects.objects.all()
    else:
        projects = Projects.objects.filter(assigned_to=request.user)

    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(assigned_to__username__icontains=search_query) |
            Q(status__icontains=search_query)
        ).distinct()
    
    # Apply pagination for regular request
    paginator = Paginator(projects, page_size)
    try:
        projects_page = paginator.page(page)
    except PageNotAnInteger:
        projects_page = paginator.page(1)
    except EmptyPage:
        projects_page = paginator.page(paginator.num_pages)

    context = {
        "projects": projects_page,
        "search_query": search_query,
        "paginator": paginator,
        "page_obj": projects_page,
    }
    return render(request, "view_projects.html", context)

## edit Projects
import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import ValidationError

@jwt_or_session_required
@permission_required('projects.change_projects')
@csrf_exempt
def edit_projects(request, project_id):
    project = get_object_or_404(Projects, id=project_id)
    
    # Helper function to get users based on capability
    def get_filtered_users(user):
        all_active_users = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True).order_by('first_name', 'username')

        # Organization managers can assign any active user.
        if can_manage_users(user):
            return all_active_users

        # Project managers can assign contributors (users without manager-like capabilities).
        manager_ids = [u.id for u in all_active_users if is_manager_like(u)]
        return all_active_users.exclude(id__in=manager_ids)

    # # Scoped managers can edit only projects they own OR if they have change_projects permission
    # if not can_view_all_projects(request.user) and project.created_by != request.user and not can_change_projects(request.user):
    #     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    #         return JsonResponse({
    #             'success': False,
    #             'error': "You don't have permission to edit this project."
    #         }, status=403)
    #     messages.error(request, "⛔ You don't have permission to edit this project.")
    #     return redirect("view_projects")

    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "POST":
            # Get filtered users based on role
            filtered_users = get_filtered_users(request.user)
            
            class FilteredProjectForm(ProjectForm):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.fields['assigned_to'].queryset = filtered_users
            
            form = FilteredProjectForm(request.POST, instance=project)
            
            # Get dates for validation
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            # Validate dates - start must be before end
            if start_date and end_date:
                if start_date >= end_date:
                    return JsonResponse({
                        'success': False,
                        'errors': {
                            'date_error': 'End date must be after start date'
                        }
                    }, status=400)
            
            if form.is_valid():
                saved_project = form.save()
                return JsonResponse({
                    'success': True,
                    'message': '✅ Project updated successfully!',
                    'redirect_url': request.POST.get('redirect_url', '/projects/'),
                    'project': {
                        'id': saved_project.id,
                        'name': saved_project.name,
                        'description': saved_project.description,
                        'status': saved_project.status,
                        'start_date': saved_project.start_date.strftime('%Y-%m-%d') if saved_project.start_date else None,
                        'end_date': saved_project.end_date.strftime('%Y-%m-%d') if saved_project.end_date else None,
                        'assigned_to': [{
                            'id': user.id,
                            'name': user.get_full_name() or user.username,
                            'email': user.email
                        } for user in saved_project.assigned_to.all()]
                    }
                })
            else:
                # Return form errors as JSON
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = error_list
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)
        
        # GET request - return project data
        elif request.method == "GET":
            filtered_users = get_filtered_users(request.user)
            
            class FilteredProjectForm(ProjectForm):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.fields['assigned_to'].queryset = filtered_users
            
            form = FilteredProjectForm(instance=project)
            return JsonResponse({
                'success': True,
                'project': {
                    'id': project.id,
                    'name': project.name,
                    'description': project.description,
                    'status': project.status,
                    'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else None,
                    'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else None,
                    'assigned_to': [user.id for user in project.assigned_to.all()],
                    'assigned_to_details': [{
                        'id': user.id,
                        'name': user.get_full_name() or user.username,
                        'email': user.email
                    } for user in project.assigned_to.all()]
                }
            })
    
    # Handle regular (non-AJAX) request
    if request.method == "POST":
        filtered_users = get_filtered_users(request.user)
        
        class FilteredProjectForm(ProjectForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields['assigned_to'].queryset = filtered_users
        
        form = FilteredProjectForm(request.POST, instance=project)
        
        # Get dates for validation
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Validate dates - start must be before end
        if start_date and end_date:
            if start_date >= end_date:
                context = {
                    "form": form,
                    "project": project,
                    "date_error": "❌ End date must be after start date"
                }
                return render(request, "edit_projects.html", context)
        
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Project updated successfully!")
            return redirect("view_projects")
        else:
            # Form is invalid - show errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            
            context = {
                "form": form,
                "project": project
            }
            return render(request, "edit_projects.html", context)
        
    else:
        filtered_users = get_filtered_users(request.user)
        
        class FilteredProjectForm(ProjectForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields['assigned_to'].queryset = filtered_users
        
        form = FilteredProjectForm(instance=project)

    return render(request, "edit_projects.html", {
        "form": form,
        "project": project
    })

@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def edit_task(request, task_id):
    """Edit Task - AJAX enabled"""
    
    task = get_object_or_404(Task, id=task_id)
    task = Task.objects.prefetch_related('assigned_by', 'assigned_to', 'observers').get(id=task_id)
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    default_redirect = dashboard_url_for(request.user)
    
    # Create form with filtered projects based on role
    class FilteredTaskForm(TaskForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if can_view_all_projects(request.user):
                self.fields['project'].queryset = Projects.objects.all()
            else:
                self.fields['project'].queryset = Projects.objects.filter(assigned_to=request.user)

                   # 🔽 ADDED: Filter out admin users from assignee and observer fields
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
            
            self.fields['observers'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
            
            self.fields['assigned_by'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
    
    if request.method == 'POST':
        form = FilteredTaskForm(request.POST, instance=task)
        
        # Get dates for validation
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Validate dates - start must be before end
        if start_date and end_date:
            if start_date > end_date:
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': 'End date must be after start date',
                        'field': 'end_date'
                    }, status=400)
                else:
                    context = {
                        'form': form,
                        'task': task,
                        'is_edit': True,
                        'date_error': "❌ End date must be after start date"
                    }
                    return render(request, 'edit_task.html', context)
        
        if form.is_valid():
            updated_task = form.save(commit=False)
            updated_task.save()
            form.save_m2m()
            
            # AJAX response
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': f'✅ Task "{task.name}" updated successfully!',
                    'task_id': task.id,
                    'task_name': task.name,
                    'project_id': task.project.id
                })
            else:
                messages.success(request, f'✅ Task "{task.name}" updated successfully!')
                return redirect('view_project_detail', project_id=task.project.id)
        else:
            # Form is invalid
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
                context = {
                    'form': form,
                    'task': task,
                    'is_edit': True
                }
                return render(request, 'edit_task.html', context)
    
    # GET request - show form
    else:
        form = FilteredTaskForm(instance=task)
    
    context = {
        'form': form,
        'task': task,
        'is_edit': True
    }
    return render(request, 'edit_task.html', context)


## delete task
@jwt_or_session_required
@permission_required('Tasks.delete_task')
@csrf_exempt
def delete_task(request, task_id):
    """Delete a task - AJAX enabled"""
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    task = get_object_or_404(Task, id=task_id)
    project_id = task.project.id
    task_name = task.name
    
    if request.method == 'POST':
        task.delete()
        
        # If AJAX request, return JSON
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': f'Task "{task_name}" deleted successfully!',
                'project_id': project_id
            })
        else:
            # Regular form submission fallback
            messages.success(request, f'Task "{task_name}" deleted successfully!')
            return redirect('view_project_detail', project_id=project_id)
    
    # GET request - show confirmation page (for non-AJAX fallback)
    context = {'task': task}
    return render(request, 'delete_task_confirm.html', context)



### view_project_details
@jwt_or_session_required
@permission_required('projects.view_projects')
def view_project_detail(request, project_id):
    project = get_object_or_404(Projects, id=project_id)
    
    # Scoped users can only access projects assigned to them.
    if not can_view_all_projects(request.user) and request.user not in project.assigned_to.all():
        messages.error(request, "You don't have permission to view this project.")
        return redirect('view_projects')
    
    # Handle AJAX request for tasks pagination
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        tasks_page = request.GET.get('tasks_page', 1)
        tasks_page_size = request.GET.get('tasks_page_size', 10)
        
        tasks = Task.objects.filter(project=project).order_by('-created_at')
        
        # Calculate statistics
        total_tasks = tasks.count()
        pending_tasks = tasks.filter(status='PENDING').count()
        ongoing_tasks = tasks.filter(status='ONGOING').count()
        completed_tasks = tasks.filter(status='COMPLETED').count()
        
        # Apply pagination
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        paginator = Paginator(tasks, tasks_page_size)
        try:
            tasks_page_obj = paginator.page(tasks_page)
        except PageNotAnInteger:
            tasks_page_obj = paginator.page(1)
        except EmptyPage:
            tasks_page_obj = paginator.page(paginator.num_pages)
        
        # Prepare tasks data
        tasks_data = []
        from django.utils import timezone
        now = timezone.now()
        
        for task in tasks_page_obj:
            # Calculate time display
            if task.status == "ONGOING" and task.start_time:
                elapsed = now - task.start_time
                if task.total_paused_duration:
                    elapsed = elapsed - task.total_paused_duration
                total_seconds = int(elapsed.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            elif task.status == "COMPLETED" and task.total_time:
                total_seconds = int(task.total_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                time_display = "00:00:00"
            
            # Get assignees
            assignees = []
            for assignee in task.assigned_to.all()[:2]:
                assignees.append(assignee.get_full_name() or assignee.username)
            
            tasks_data.append({
                'id': task.id,
                'name': task.name,
                'status': task.status,
                'status_display': task.get_status_display(),
                'deadline': task.deadline.strftime('%b %d, %H:%M') if task.deadline else None,
                'time_display': time_display,
                'assignees': assignees,
                'total_assignees': task.assigned_to.count(),
                'project_id': task.project.id
            })
        
        return JsonResponse({
            'success': True,
            'tasks': tasks_data,
            'total_tasks': total_tasks,
            'pending_tasks': pending_tasks,
            'ongoing_tasks': ongoing_tasks,
            'completed_tasks': completed_tasks,
            'total_pages': paginator.num_pages,
            'current_page': tasks_page_obj.number,
            'has_previous': tasks_page_obj.has_previous(),
            'has_next': tasks_page_obj.has_next(),
            'previous_page_number': tasks_page_obj.previous_page_number() if tasks_page_obj.has_previous() else None,
            'next_page_number': tasks_page_obj.next_page_number() if tasks_page_obj.has_next() else None,
            'page_size': int(tasks_page_size)
        })
    
    # Regular request - return full template
    resources = project.resources.all()
    tasks = Task.objects.filter(project=project).order_by('-created_at')
    
    from django.utils import timezone
    for task in tasks:
        if task.status == "ONGOING" and task.start_time:
            elapsed = timezone.now() - task.start_time
            if task.total_paused_duration:
                elapsed = elapsed - task.total_paused_duration
            total_seconds = int(elapsed.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            task.time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        elif task.status == "COMPLETED" and task.total_time:
            total_seconds = int(task.total_time.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            task.time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    total_tasks = tasks.count()
    ongoing_tasks = tasks.filter(status='ONGOING').count()
    completed_tasks = tasks.filter(status='COMPLETED').count()
    pending_tasks = tasks.filter(status='PENDING').count()
    
    # Add pagination for regular request (tasks will be loaded via AJAX)
    return render(request, "view_project_detail.html", {
        "project": project,
        "resources": resources,
        "tasks": tasks[:10],  # Only first 10 for initial load
        "total_tasks": total_tasks,
        "ongoing_tasks": ongoing_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
    })
    

## View Users detail
import re
from users.models import UserProfile

@jwt_or_session_required
def view_user_details(request, user_id):
    # Allow users to always view their own profile
    # For viewing OTHER users, require 'users.view_user' permission
    if request.user.id != user_id and not request.user.is_superuser and not request.user.has_perm('users.view_user'):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'access_denied': True,
                'message': 'Access denied. You can only view your own profile.'
            }, status=403)
        messages.error(request, "Access Denied: You don't have permission to view other users' profiles.")
        return redirect('dashboard')

    # Handle POST request for self-edit (only for own profile)
    if request.method == "POST" and request.user.id == user_id:
        user_obj = get_object_or_404(User, id=user_id)
        profile, created = UserProfile.objects.get_or_create(user=user_obj)
        
        errors = {}
        
        # Phone Number Validation (10 digits, numeric)
        phone = request.POST.get('phone', '').strip()
        if phone:
            if not re.match(r'^[6-9]\d{9}$', phone):
                errors['phone'] = 'Phone number must be 10 digits and start with 6,7,8, or 9'
        
        # Emergency Contact Validation (10 digits, numeric)
        emergency_contact = request.POST.get('emergency_contact', '').strip()
        if emergency_contact:
            if not re.match(r'^[6-9]\d{9}$', emergency_contact):
                errors['emergency_contact'] = 'Emergency contact must be 10 digits and start with 6,7,8, or 9'
        
        # Address Validation (not empty if provided)
        address = request.POST.get('address', '').strip()
        if address and len(address) < 5:
            errors['address'] = 'Address must be at least 5 characters long'
        
        if errors:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': errors}, status=400)
        
        # Update only allowed fields (non-sensitive)
        if request.FILES.get('profile_image'):
            # Validate image file type and size
            image_file = request.FILES['profile_image']
            if image_file.size > 5 * 1024 * 1024:  # 5MB limit
                errors['profile_image'] = 'Image size must be less than 5MB'
            elif not image_file.content_type.startswith('image/'):
                errors['profile_image'] = 'File must be an image (JPG, PNG, GIF)'
            else:
                profile.profile_image = image_file
        
        if phone:
            profile.phone = phone
        if emergency_contact:
            profile.emergency_contact = emergency_contact
        if address:
            profile.address = address
        
        if errors:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': errors}, status=400)
        
        profile.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})
        return redirect(f"/user/{user_id}/")
    
    # Only allow GET requests for viewing
    if request.method != "GET":
        return redirect(f"/view_user_details/{user_id}/")
    
    # First check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        user_obj = get_object_or_404(User, id=user_id)
        profile, created = UserProfile.objects.get_or_create(user=user_obj)

        ## Analytics 
        projects_assigned = Projects.objects.filter(assigned_to=user_obj).count()
        tasks_assigned = Task.objects.filter(assigned_to=user_obj).count()
        completed_tasks = Task.objects.filter(assigned_to=user_obj, status="COMPLETED").count()

        performance = 0
        if tasks_assigned > 0:
            performance = int((completed_tasks / tasks_assigned) * 100)

        return JsonResponse({
            "success": True,
            "user": {
                "id": user_obj.id,
                "username": user_obj.username,
                "email": user_obj.email,
                "role": user_obj.role,
                "is_active": user_obj.is_active,
                "full_name": user_obj.get_full_name() or user_obj.username,
                "date_joined": user_obj.date_joined.strftime('%Y-%m-%d') if user_obj.date_joined else None,
                "profile_image": profile.profile_image.url if profile.profile_image else None
            },
            "profile": {
                "profile_image": profile.profile_image.url if profile.profile_image else None,
                "employee_id": profile.employee_id or "—",
                "phone": profile.phone or "—",
                "department": profile.department.name if profile.department else "—",
                "designation": profile.designation.name if profile.designation else "—",
                "date_of_joining": profile.date_of_joining.strftime('%Y-%m-%d') if profile.date_of_joining else "—",
                "ctc": profile.ctc or "—",
                "salary_in_hand": profile.salary_in_hand or "—",
                "bank_name": profile.bank_name or "—",
                "account_no": profile.account_no or "—",
                "ifsc": profile.ifsc or "—",
                "aadhar_no": profile.aadhar_no or "—",
                "pan_no": profile.pan_no or "—",
                "emergency_contact": profile.emergency_contact or "—",
                "address": profile.address or "—"
            },
            "analytics": {
                "projects_assigned": projects_assigned,
                "tasks_assigned": tasks_assigned,
                "completed_tasks": completed_tasks,
                "performance": performance
            }
        })
    
    # For non-AJAX requests, return minimal template with user_id only
    return render(request, "view_user_details.html", {
        "user_id": user_id
    })

## Add project resource
@jwt_or_session_required
@csrf_exempt
def add_project_resource(request, project_id):
    project = get_object_or_404(Projects, id=project_id)

    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "POST":
            form = ProjectResourceForm(request.POST, request.FILES)
            if form.is_valid():
                resource = form.save(commit=False)
                resource.project = project
                resource.save()
                return JsonResponse({
                    'success': True,
                    'message': f'Resource "{resource.name}" added successfully!'
                })
            else:
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = error_list
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)
        else:
            return JsonResponse({
                'success': True,
                'project_id': project.id,
                'project_name': project.name
            })
    
    # Regular request - your original code unchanged
    if request.method == "POST":
        form = ProjectResourceForm(request.POST, request.FILES)
        if form.is_valid():
            resource = form.save(commit=False)
            resource.project = project
            resource.save()
            return redirect("view_project_detail", project_id=project.id)
    else:
        form = ProjectResourceForm()

    return render(
        request,
        "add_project_resource.html",
        {"form": form, "project": project}
    )


## delete Projects
@jwt_or_session_required
@permission_required('projects.delete_projects')
@csrf_exempt
def delete_project(request, id):
    """Delete a project - AJAX enabled"""
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    project = get_object_or_404(Projects, id=id)
    project_name = project.name
    
    if request.method == 'POST':
        project.delete()
        
        # If AJAX request, return JSON
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': f'Project "{project_name}" deleted successfully!'
            })
        else:
            # Regular form submission fallback
            messages.success(request, f'Project "{project_name}" deleted successfully!')
            if can_view_all_projects(request.user):
                return redirect("view_projects")
            return redirect(dashboard_url_for(request.user))
    
    # GET request - redirect to list (for non-AJAX fallback)
    # Since this view doesn't have a confirmation template, we'll redirect
    return redirect("view_projects")
    
## login page......
from django.views.decorators.csrf import ensure_csrf_cookie
def login_page(request):
    # If it's an AJAX request, return CSRF token (for GET) or handle login (for POST)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "GET":
            return JsonResponse({
                'success': True,
                'csrf_token': request.COOKIES.get('csrftoken', '')
            })
    
    return render(request, "ajax_login.html")


## Dashboard view
@jwt_or_session_required
def dashboard(request):
    user = request.user
    
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = {
            'success': True,
            'role': user.role_obj.name if user.role_obj else (user.role or 'USER'),
            'stats': {},
            'permissions': {
                'can_manage_users': can_manage_users(user),
                'can_add_task': can_add_task(user),
                'can_view_projects': can_view_projects(user),
                'can_manage_projects': can_manage_projects(user),
                'can_manage_roles': can_manage_roles(user),
                'can_start_task': can_start_task(user),
                'can_resume_task': can_resume_task(user),
                'can_complete_task': can_complete_task(user),
            }
        }

        # 1. Admin / Manager Data
        if can_manage_users(user):
            data['dashboard_variant'] = 'owner'
            data['stats'] = {
                'total_users': User.objects.count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'inactive_users': User.objects.filter(is_active=False).count(),
                'total_projects': Projects.objects.count(),
                'total_tasks': Task.objects.count(),
                'ongoing_projects': Projects.objects.filter(status='ONGOING').count(),
                'completed_tasks': Task.objects.filter(status='COMPLETED').count(),
            }
            
            # Users list for admin with pagination - 5 per page
            from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
            
            users_qs = User.objects.all().order_by('-date_joined')
            try:
                # Changed default page_size from 10 to 5
                page_size = int(request.GET.get("page_size", 5))
                page = int(request.GET.get("page", 1))
            except ValueError:
                page_size = 5
                page = 1
                
            paginator = Paginator(users_qs, page_size)
            
            try:
                users_page = paginator.page(page)
            except PageNotAnInteger:
                users_page = paginator.page(1)
            except EmptyPage:
                users_page = paginator.page(paginator.num_pages)

            users_data = []
            for u in users_page:
                role_label = u.role_obj.name if u.role_obj else (u.role or 'UNASSIGNED')
                if can_manage_users(u): role_tier = 'owner'
                elif is_manager_like(u): role_tier = 'manager'
                elif can_view_task(u): role_tier = 'contributor'
                else: role_tier = 'custom'

                # Get profile image if exists
                profile_image = None
                if hasattr(u, 'profile') and u.profile.profile_image:
                    profile_image = u.profile.profile_image.url
                
                users_data.append({
                    'id': u.id,
                    'username': u.username,
                    'email': u.email,
                    'role': role_label,
                    'role_tier': role_tier,
                    'is_active': u.is_active,
                    'profile_image': profile_image,
                })
            data['users'] = users_data
            
            data['pagination'] = {
                'total': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': users_page.number,
                'has_previous': users_page.has_previous(),
                'has_next': users_page.has_next(),
                'previous_page_number': users_page.previous_page_number() if users_page.has_previous() else None,
                'next_page_number': users_page.next_page_number() if users_page.has_next() else None,
                'page_size': page_size,
            }

        # 2. Team Lead / Task Manager Data
        elif can_add_task(user):
            data['dashboard_variant'] = 'manager'
            my_projects = Projects.objects.filter(assigned_to=user)
            my_project_ids = my_projects.values_list('id', flat=True)
            tasks_from_my_projects = Task.objects.filter(project_id__in=my_project_ids)
            
            active_users = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True)
            team_members = [member for member in active_users if not is_manager_like(member)]
            
            data['stats'] = {
                'total_projects': my_projects.count(),
                'active_tasks': tasks_from_my_projects.filter(status='ONGOING').count(),
                'completed_tasks': tasks_from_my_projects.filter(status='COMPLETED').count(),
                'team_members': len(team_members),
            }
            
            # Recent projects for TL
            recent_projects = my_projects.order_by('-start_date')[:5]
            data['recent_projects'] = [{
                'id': p.id,
                'name': p.name,
                'status': p.status,
                'end_date': p.end_date.strftime('%b %d, %Y') if p.end_date else 'N/A'
            } for p in recent_projects]

        # 3. Employee / Contributor Data
        else:
            data['dashboard_variant'] = 'contributor'
            tasks = Task.objects.filter(assigned_to=user)
            projects = Projects.objects.filter(assigned_to=user)
            
            data['stats'] = {
                'tasks_count': tasks.count(),
                'ongoing_tasks': tasks.filter(status='ONGOING').count(),
                'completed_tasks': tasks.filter(status='COMPLETED').count(),
                'pending_tasks': tasks.filter(status='PENDING').count(),
                'projects_count': projects.count(),
            }

            # Recent tasks for Employee
            recent_tasks = tasks.order_by('-created_at')[:5]
            data['recent_tasks'] = [{
                'id': t.id,
                'name': t.name,
                'status': t.status,
                'status_display': t.get_status_display(),
                'project_name': t.project.name if t.project else "General",
                'end_date': t.end_date.strftime('%b %d') if t.end_date else "No deadline"
            } for t in recent_tasks]

        return JsonResponse(data)
    
    # Regular request - return template
    return render(request, "dashboard.html")



## logout
@jwt_or_session_required
def logout_view(request):
    refresh_token = None
    
    # Check if it's an AJAX/API request
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.headers.get('Accept') == 'application/json'
    )
    
    # Get refresh token from request body
    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
            refresh_token = body.get('refresh_token')
        except (json.JSONDecodeError, AttributeError):
            refresh_token = None

    if not refresh_token:
        refresh_token = request.COOKIES.get('refresh_token')

    # Blacklist the refresh token
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except (TokenError, Exception):
            pass

    # For JWT-only authentication, we don't need logout()
    # Just remove the tokens

    # Create response
    if is_ajax:
        response = JsonResponse({
            'success': True,
            'message': 'Logged out successfully',
            'redirect_url': '/'
        })
    else:
        response = redirect('login_page')

    # Clear JWT cookies
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    response.delete_cookie('user_role')
    response.delete_cookie('username')
    response.delete_cookie('user_id')
    
    return response


## required logins
from .models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

## Admin dashboard 
@jwt_or_session_required
@permission_required('users.view_user')
def admin_dashboard(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get pagination parameters
        users_page = request.GET.get('users_page', 1)
        users_page_size = request.GET.get('users_page_size', 10)
        
        # User statistics (using full queryset)
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        inactive_users = User.objects.filter(is_active=False).count()
        
        # Project statistics
        total_projects = Projects.objects.count()
        ongoing_projects = Projects.objects.filter(status='ONGOING').count()
        pending_projects = Projects.objects.filter(status='PENDING').count()
        completed_projects = Projects.objects.filter(status='COMPLETED').count()
        
        # Task statistics
        total_tasks = Task.objects.count()
        completed_tasks = Task.objects.filter(status='COMPLETED').count()
        ongoing_tasks = Task.objects.filter(status='ONGOING').count()
        pending_tasks = Task.objects.filter(status='PENDING').count()
        
        # Recent items (always get latest 5)
        recent_projects = Projects.objects.all().order_by('-start_date')[:5]
        recent_projects_data = []
        for project in recent_projects:
            recent_projects_data.append({
                'id': project.id,
                'name': project.name,
                'status': project.status,
                'end_date': project.end_date.strftime('%b %d, %Y') if project.end_date else 'N/A'
            })
        
        recent_tasks = Task.objects.all().order_by('-created_at')[:5]
        recent_tasks_data = []
        for task in recent_tasks:
            assignees = []
            for assignee in task.assigned_to.all():
                assignees.append(assignee.get_full_name() or assignee.username)
            
            recent_tasks_data.append({
                'id': task.id,
                'name': task.name,
                'status': task.status,
                'status_display': task.get_status_display(),
                'assignees': assignees
            })
        
        # Users table with pagination
        users = User.objects.all().order_by('-date_joined')
        paginator = Paginator(users, users_page_size)
        try:
            users_page_obj = paginator.page(users_page)
        except PageNotAnInteger:
            users_page_obj = paginator.page(1)
        except EmptyPage:
            users_page_obj = paginator.page(paginator.num_pages)
        
        users_data = []
        for user in users_page_obj:
            role_label = user.role_obj.name if user.role_obj else (user.role or 'UNASSIGNED')
            if can_manage_users(user):
                role_tier = 'owner'
            elif is_manager_like(user):
                role_tier = 'manager'
            elif can_view_task(user):
                role_tier = 'contributor'
            else:
                role_tier = 'custom'

            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': role_label,
                'role_tier': role_tier,
                'is_active': user.is_active,
                'edit_url': f"/user/{user.id}/edit/",
                'delete_url': f"/user/{user.id}/delete/"
            })
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_users': total_users,
                'active_users': active_users,
                'inactive_users': inactive_users,
                'total_projects': total_projects,
                'ongoing_projects': ongoing_projects,
                'pending_projects': pending_projects,
                'completed_projects': completed_projects,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'ongoing_tasks': ongoing_tasks,
                'pending_tasks': pending_tasks
            },
            'recent_projects': recent_projects_data,
            'recent_tasks': recent_tasks_data,
            'users': users_data,
            'users_pagination': {
                'total': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': users_page_obj.number,
                'has_previous': users_page_obj.has_previous(),
                'has_next': users_page_obj.has_next(),
                'previous_page_number': users_page_obj.previous_page_number() if users_page_obj.has_previous() else None,
                'next_page_number': users_page_obj.next_page_number() if users_page_obj.has_next() else None,
                'page_size': int(users_page_size)
            }
        })
    
    # Regular request - return template
    return render(request, 'admin_dashboard.html')


# teamlead dashboard
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
@jwt_or_session_required
@permission_required('Tasks.add_task')
def teamlead_dashboard(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get pagination parameters for team members
        members_page = request.GET.get('members_page', 1)
        members_page_size = request.GET.get('members_page_size', 8)  # 8 members (2 rows of 4)
        
        # Get ONLY projects assigned to this team lead
        my_projects = Projects.objects.filter(assigned_to=request.user)
        
        # Get IDs of these projects
        my_project_ids = my_projects.values_list('id', flat=True)
        
        # Get tasks ONLY from team lead's projects
        tasks_from_my_projects = Task.objects.filter(project_id__in=my_project_ids)
        
        # Statistics - only from team lead's projects
        total_projects = my_projects.count()
        active_tasks = tasks_from_my_projects.filter(status='ONGOING').count()
        completed_tasks = tasks_from_my_projects.filter(status='COMPLETED').count()
        pending_tasks_list = tasks_from_my_projects.filter(status='PENDING').order_by('-created_at')[:5]
        
        active_users = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True)
        all_team_members = [member for member in active_users if not is_manager_like(member)]
        team_members_total = len(all_team_members)
        active_members = team_members_total
        
        # Recent projects - only team lead's projects
        recent_projects = my_projects.order_by('-start_date')[:5]
        recent_projects_data = []
        for project in recent_projects:
            recent_projects_data.append({
                'id': project.id,
                'name': project.name,
                'status': project.status,
                'end_date': project.end_date.strftime('%b %d, %Y') if project.end_date else 'N/A'
            })
        
        # Pending tasks data
        pending_tasks_data = []
        for task in pending_tasks_list:
            assignees = []
            for assignee in task.assigned_to.all()[:2]:
                assignees.append(assignee.get_full_name() or assignee.username)
            
            pending_tasks_data.append({
                'id': task.id,
                'name': task.name,
                'status_display': task.get_status_display(),
                'assignees': assignees,
                'total_assignees': task.assigned_to.count()
            })
        
        # Team members list with pagination
        all_team_members_sorted = sorted(all_team_members, key=lambda member: member.username.lower())
        paginator = Paginator(all_team_members_sorted, members_page_size)
        try:
            members_page_obj = paginator.page(members_page)
        except PageNotAnInteger:
            members_page_obj = paginator.page(1)
        except EmptyPage:
            members_page_obj = paginator.page(paginator.num_pages)
        
        team_members_data = []
        for member in members_page_obj:
            team_members_data.append({
                'id': member.id,
                'name': member.get_full_name() or member.username,
                'email': member.email,
                'initial': (member.get_full_name() or member.username)[0].upper()
            })
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_projects': total_projects,
                'active_tasks': active_tasks,
                'completed_tasks': completed_tasks,
                'team_members': team_members_total,
                'active_members': active_members,
                'ongoing_tasks': active_tasks
            },
            'recent_projects': recent_projects_data,
            'pending_tasks': pending_tasks_data,
            'team_members_list': team_members_data,
            'team_members_pagination': {
                'total': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': members_page_obj.number,
                'has_previous': members_page_obj.has_previous(),
                'has_next': members_page_obj.has_next(),
                'previous_page_number': members_page_obj.previous_page_number() if members_page_obj.has_previous() else None,
                'next_page_number': members_page_obj.next_page_number() if members_page_obj.has_next() else None,
                'page_size': int(members_page_size)
            }
        })
    
    # Regular request - return template
    return render(request, 'teamlead_dashboard.html')


## employee dashboard
@jwt_or_session_required
@permission_required('Tasks.view_task')
@csrf_exempt
def employee_dashboard(request):
    user = request.user

    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Tasks assigned to employee
        tasks = Task.objects.filter(assigned_to=user)
        tasks_count = tasks.count()
        ongoing_tasks = tasks.filter(status='ONGOING').count()
        completed_tasks = tasks.filter(status='COMPLETED').count()
        pending_tasks = tasks.filter(status='PENDING').count()
        recent_tasks = tasks.order_by('-created_at')[:5]
        
        recent_tasks_data = []
        for task in recent_tasks:
            recent_tasks_data.append({
                'id': task.id,
                'name': task.name,
                'status': task.status,
                'status_display': task.get_status_display(),
                'project_name': task.project.name if task.project else "General",
                'end_date': task.end_date.strftime('%b %d') if task.end_date else "No deadline"
            })
        
        # Projects assigned to employee
        projects = Projects.objects.filter(assigned_to=user)
        projects_count = projects.count()
        ongoing_projects = projects.filter(status='ONGOING').count()
        pending_projects = projects.filter(status='PENDING').count()
        completed_projects = projects.filter(status='COMPLETED').count()

        return JsonResponse({
            'success': True,
            'stats': {
                'tasks_count': tasks_count,
                'ongoing_tasks': ongoing_tasks,
                'completed_tasks': completed_tasks,
                'pending_tasks': pending_tasks,
                'projects_count': projects_count,
                'ongoing_projects': ongoing_projects,
                'pending_projects': pending_projects,
                'completed_projects': completed_projects
            },
            'recent_tasks': recent_tasks_data
        })
    
    # Regular request - return template
    return render(request, "employee_dashboard.html")

## Employee projects
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@jwt_or_session_required
@permission_required('projects.view_projects')
@csrf_exempt
def employee_projects(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get('search', '').strip()
        page = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 9)  # 9 for 3x3 grid
        
        projects = Projects.objects.filter(assigned_to=request.user)
        
        # Apply search filter
        if search_query:
            projects = projects.filter(name__icontains=search_query)
        
        projects = projects.order_by('-start_date')
        
        # Calculate statistics (using full queryset)
        total_projects = projects.count()
        ongoing_projects = projects.filter(status='ONGOING').count()
        completed_projects = projects.filter(status='COMPLETED').count()
        
        # Apply pagination
        paginator = Paginator(projects, page_size)
        try:
            projects_page = paginator.page(page)
        except PageNotAnInteger:
            projects_page = paginator.page(1)
        except EmptyPage:
            projects_page = paginator.page(paginator.num_pages)
        
        # Prepare projects data
        projects_data = []
        for project in projects_page:
            # Get assigned users list
            assigned_users = []
            for user in project.assigned_to.all()[:3]:
                assigned_users.append({
                    'username': user.username
                })
            
            projects_data.append({
                'id': project.id,
                'name': project.name,
                'description': project.description[:100] if project.description else '',
                'status': project.status,
                'status_display': project.get_status_display(),
                'status_class': 'bg-yellow-100 text-yellow-700' if project.status == 'PENDING' else 'bg-blue-100 text-blue-700' if project.status == 'ONGOING' else 'bg-green-100 text-green-700',
                'header_color': 'bg-yellow-400' if project.status == 'PENDING' else 'bg-blue-400' if project.status == 'ONGOING' else 'bg-green-400',
                'start_date': project.start_date.strftime('%b %d, %Y') if project.start_date else 'N/A',
                'end_date': project.end_date.strftime('%b %d, %Y') if project.end_date else 'N/A',
                'assigned_users': assigned_users,
                'total_assigned': project.assigned_to.count(),
                'view_url': f"/project/{project.id}/"
            })
        
        return JsonResponse({
            'success': True,
            'projects': projects_data,
            'total_projects': total_projects,
            'ongoing_projects': ongoing_projects,
            'completed_projects': completed_projects,
            'total_pages': paginator.num_pages,
            'current_page': projects_page.number,
            'has_previous': projects_page.has_previous(),
            'has_next': projects_page.has_next(),
            'previous_page_number': projects_page.previous_page_number() if projects_page.has_previous() else None,
            'next_page_number': projects_page.next_page_number() if projects_page.has_next() else None,
            'page_size': int(page_size),
            'search_query': search_query
        })
    
    # Regular request - return template with empty data
    return render(request, "employee_projects.html")



## Register user form
from .forms import  UserRegisterForm
def register(request):
    departments = Department.objects.all()
    designations = Designation.objects.all()

    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # Save the User instance
            user = form.save(commit=False)
            user.is_active = False  # User must activate via email
            user.save()

            # Create the UserProfile with additional info
            profile = UserProfile.objects.create(
                user=user,
                department_id=request.POST.get("department"),
                designation_id=request.POST.get("designation"),
                employee_id=request.POST.get("employee_id"),
                phone=request.POST.get("phone"),
                date_of_joining=request.POST.get("date_of_joining") or None
            )

            # Generate activation link
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            current_site = get_current_site(request)
            activation_link = f"http://{current_site.domain}/activate/{uid}/{token}/"

            # Compose the email
            subject = "Activate your PMS account"
            message = f"""
Hi {user.username},

Welcome to our platform!

Please click the link below to activate your account:

{activation_link}

If you did not register on our site, please ignore this email.
"""
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]

            # Send the email
            send_mail(subject, message, from_email, recipient_list, fail_silently=False)

            messages.success(request, "Registration successful! Please check your email to activate your account.")
            return redirect("login_page")
        else:
            print("Form errors:", form.errors)
    else:
        form = UserRegisterForm()

    return render(
        request,
        "register.html",
        {
            "form": form,
            "departments": departments,
            "designations": designations
        }
    )

## Edit User - Admin only
import re

@jwt_or_session_required
@permission_required('users.change_user')
@csrf_exempt
def edit_user(request, user_id):
    """Edit User - AJAX enabled"""
    
    # Get user and their profile
    user = get_object_or_404(User, id=user_id)
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Get all departments and designations for dropdowns
    departments = Department.objects.all()
    designations = Designation.objects.all()
    roles = Role.objects.all().order_by('name')
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == "POST":
        # Get form data
        email = request.POST.get("email")
        username = request.POST.get("username")
        user.first_name = request.POST.get("first_name", "")
        user.last_name = request.POST.get("last_name", "")
        role_obj_id = request.POST.get("role_obj")
        is_active = request.POST.get("is_active")
        employee_id = request.POST.get("employee_id", "").strip()
        
        # Validate required fields
        errors = {}
        
        # Email validation
        if not email:
            errors['email'] = ['Email is required']
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors['email'] = ['Please enter a valid email address']
        
        # Username validation
        if not username:
            errors['username'] = ['Username is required']
        elif len(username) < 3:
            errors['username'] = ['Username must be at least 3 characters long']
        
        # Role validation
        if not role_obj_id:
            errors['role_obj'] = ['Role is required']
        
        # Employee ID validation
        if not employee_id:
            errors['employee_id'] = ['Employee ID is required']
        elif len(employee_id) < 2:
            errors['employee_id'] = ['Employee ID must be at least 2 characters long']
        else:
            # Check uniqueness (excluding current user)
            if UserProfile.objects.exclude(id=profile.id).filter(employee_id=employee_id).exists():
                errors['employee_id'] = ['Employee ID already exists. Please use a unique ID.']
        
        # Phone number validation (10 digits, starts with 6-9)
        phone = request.POST.get("phone", "").strip()
        if phone:
            if not re.match(r'^[6-9]\d{9}$', phone):
                errors['phone'] = ['Phone number must be 10 digits and start with 6, 7, 8, or 9']
        
        # Emergency contact validation
        emergency_contact = request.POST.get("emergency_contact", "").strip()
        if emergency_contact:
            if not re.match(r'^[6-9]\d{9}$', emergency_contact):
                errors['emergency_contact'] = ['Emergency contact must be 10 digits and start with 6, 7, 8, or 9']
        
        # Aadhar number validation (12 digits)
        aadhar_no = request.POST.get("aadhar_no", "").strip()
        if aadhar_no:
            if not re.match(r'^\d{12}$', aadhar_no):
                errors['aadhar_no'] = ['Aadhar number must be exactly 12 digits']
        
        # PAN number validation (5 letters + 4 digits + 1 letter)
        pan_no = request.POST.get("pan_no", "").strip()
        if pan_no:
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan_no.upper()):
                errors['pan_no'] = ['PAN number must be in format: ABCDE1234F (5 letters, 4 digits, 1 letter)']
        
        # IFSC code validation (11 characters: 4 letters + 7 alphanumeric)
        ifsc = request.POST.get("ifsc", "").strip()
        if ifsc:
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc.upper()):
                errors['ifsc'] = ['IFSC code must be 11 characters (e.g., SBIN0123456)']
        
        # CTC validation (positive number)
        ctc = request.POST.get("ctc", "").strip()
        if ctc:
            try:
                ctc_val = float(ctc)
                if ctc_val < 0:
                    errors['ctc'] = ['CTC cannot be negative']
            except ValueError:
                errors['ctc'] = ['Please enter a valid number for CTC']
        
        # Salary validation (positive number)
        salary_in_hand = request.POST.get("salary_in_hand", "").strip()
        if salary_in_hand:
            try:
                salary_val = float(salary_in_hand)
                if salary_val < 0:
                    errors['salary_in_hand'] = ['Salary cannot be negative']
            except ValueError:
                errors['salary_in_hand'] = ['Please enter a valid number for salary']
        
        # Account number validation (at least 9 digits)
        account_no = request.POST.get("account_no", "").strip()
        if account_no:
            if len(account_no) < 9 or len(account_no) > 18:
                errors['account_no'] = ['Account number should be between 9 to 18 digits']
            elif not account_no.isdigit():
                errors['account_no'] = ['Account number should contain only digits']
        
        # Address validation
        address = request.POST.get("address", "").strip()
        if address and len(address) < 5:
            errors['address'] = ['Address must be at least 5 characters long']

        selected_role = None
        if role_obj_id:
            try:
                selected_role = Role.objects.get(id=role_obj_id)
            except Role.DoesNotExist:
                errors['role_obj'] = ['Invalid role selected']
        
        if errors:
            if is_ajax:
                return JsonResponse({'success': False, 'errors': errors}, status=400)
            else:
                for field, err_list in errors.items():
                    for err in err_list:
                        messages.error(request, f"{field}: {err}")
                context = {
                    "user": user,
                    "profile": profile,
                    "departments": departments,
                    "designations": designations,
                    "roles": roles,
                }
                return render(request, "edit_user.html", context)
        
        # Update user
        user.email = email
        user.username = username
        user.role_obj = selected_role
        user.role = selected_role.name if selected_role else user.role
        user.is_active = (is_active == "True")
        user.save()

        # Update profile - Basic Details (Department & Designation are now OPTIONAL)
        profile.department_id = request.POST.get("department") or None  # ✅ Can be empty
        profile.designation_id = request.POST.get("designation") or None  # ✅ Can be empty
        profile.employee_id = employee_id or None
        profile.phone = phone or None
        profile.date_of_joining = request.POST.get("date_of_joining") or None
        
        # Handle profile image upload with validation
        if request.FILES.get('profile_image'):
            image_file = request.FILES['profile_image']
            if image_file.size > 5 * 1024 * 1024:  # 5MB limit
                if is_ajax:
                    return JsonResponse({'success': False, 'errors': {'profile_image': ['Image size must be less than 5MB']}}, status=400)
                messages.error(request, "Image size must be less than 5MB")
            elif not image_file.content_type.startswith('image/'):
                if is_ajax:
                    return JsonResponse({'success': False, 'errors': {'profile_image': ['File must be an image (JPG, PNG, GIF)']}}, status=400)
                messages.error(request, "File must be an image (JPG, PNG, GIF)")
            else:
                profile.profile_image = image_file
        
        # Salary Details
        profile.ctc = ctc if ctc else None
        profile.salary_in_hand = salary_in_hand if salary_in_hand else None
        
        # Bank Details
        profile.bank_name = request.POST.get('bank_name') or None
        profile.account_no = account_no or None
        profile.ifsc = ifsc.upper() if ifsc else None
        
        # Verification Details
        profile.aadhar_no = aadhar_no or None
        profile.pan_no = pan_no.upper() if pan_no else None
        
        # Additional Details
        profile.emergency_contact = emergency_contact or None
        profile.address = address or None
        
        profile.save()

        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': f'User "{user.username}" updated successfully!',
                'user_id': user.id
            })
        else:
            messages.success(request, "User updated successfully")
            return redirect("admin_view_users")
    
    # GET request - show the form
    context = {
        "user": user,
        "profile": profile,
        "departments": departments,
        "designations": designations,
        "roles": roles,
    }
    return render(request, "edit_user.html", context)


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
    return render(request, 'role_list.html', {'roles': roles})


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
    return render(request, 'role_form.html', context)


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
    return render(request, 'role_form.html', context)


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


## Members dashboard function
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

## Admin view users
@csrf_exempt
@jwt_or_session_required
@permission_required(['users.view_user', 'users.add_user', 'users.change_user', 'users.delete_user'])
def admin_view_users(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get('search', '').strip()
        page = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 10)
        
        if search_query:
            users = User.objects.filter(
                Q(username__icontains=search_query) |
                Q(role__icontains=search_query) |
                Q(email__icontains=search_query)
            )
        else:
            users = User.objects.all()
        
        # Order users
        users = users.order_by('-date_joined')
        
        # Apply pagination
        paginator = Paginator(users, page_size)
        try:
            users_page = paginator.page(page)
        except PageNotAnInteger:
            users_page = paginator.page(1)
        except EmptyPage:
            users_page = paginator.page(paginator.num_pages)
        
        # Prepare users data
        users_data = []
        for user in users_page:
            role_label = user.role_obj.name if user.role_obj else (user.role or 'UNASSIGNED')

            if can_manage_users(user):
                role_class = 'bg-purple-100 text-purple-700'
            elif is_manager_like(user):
                role_class = 'bg-blue-100 text-blue-700'
            elif can_view_task(user):
                role_class = 'bg-green-100 text-green-700'
            else:
                role_class = 'bg-gray-100 text-gray-700'
            
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': role_label,
                'role_display': role_label,
                'role_class': role_class,
                'is_active': user.is_active,
                'view_url': f"/user/{user.id}/",
                'delete_url': f"/user/{user.id}/delete/"
            })
        
        return JsonResponse({
            'success': True,
            'users': users_data,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': users_page.number,
            'has_previous': users_page.has_previous(),
            'has_next': users_page.has_next(),
            'previous_page_number': users_page.previous_page_number() if users_page.has_previous() else None,
            'next_page_number': users_page.next_page_number() if users_page.has_next() else None,
            'page_size': page_size,
            'search_query': search_query
        })
    
    # Regular request - return template
    return render(request, "admin_view_users.html")

## Team lead view users
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
@jwt_or_session_required
@permission_required(['users.view_user', 'users.add_user', 'users.change_user', 'users.delete_user', 'Tasks.add_task'])
def teamlead_view_users(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get('search', '').strip()
        page = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 10)
        
        employees = _contributor_users_queryset()
        
        # Apply search filter
        if search_query:
            employees = employees.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )
        
        employees = employees.order_by('username')
        
        # Calculate statistics (using full queryset)
        total_employees = _contributor_users_queryset().count()
        active_count = total_employees
        total_tasks = Task.objects.filter(assigned_to__in=_contributor_users_queryset()).count()
        
        # Apply pagination
        paginator = Paginator(employees, page_size)
        try:
            employees_page = paginator.page(page)
        except PageNotAnInteger:
            employees_page = paginator.page(1)
        except EmptyPage:
            employees_page = paginator.page(paginator.num_pages)
        
        # Prepare employees data
        employees_data = []
        for user in employees_page:
            employees_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.get_full_name() or user.username,
                'role': user.role,
                'role_display': user.role,
                'is_active': user.is_active,
                'avatar_initial': user.username[0].upper(),
                'tasks_url': f"/employee/tasks/?employee_id={user.id}",
                'assign_task_url': f"/task/assign/?employee={user.id}"
            })
        
        return JsonResponse({
            'success': True,
            'users': employees_data,
            'total_employees': total_employees,
            'active_count': active_count,
            'total_tasks': total_tasks,
            'showing_count': len(employees_data),
            'search_query': search_query,
            'total_pages': paginator.num_pages,
            'current_page': employees_page.number,
            'has_previous': employees_page.has_previous(),
            'has_next': employees_page.has_next(),
            'previous_page_number': employees_page.previous_page_number() if employees_page.has_previous() else None,
            'next_page_number': employees_page.next_page_number() if employees_page.has_next() else None,
            'page_size': int(page_size)
        })
    
    # Regular request - return template
    return render(request, 'teamlead_view_users.html')

## activate_user
from django.utils.http import urlsafe_base64_decode
csrf_exempt
def activate_user(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        # Handle AJAX request
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
        
        # Handle regular request
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
            
            return render(request, 'set_password.html', {'user': user})
        
        return render(request, 'set_password.html', {'user': user})
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Activation link is invalid or has expired!'
            }, status=400)
        
        messages.error(request, 'Activation link is invalid or has expired!')
        return redirect('login_page')
    


## Create new user with role and save to database
from django.contrib.auth import get_user_model
User = get_user_model()
import re
import secrets
import string
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from users.decorators import jwt_or_session_required, allowed_roles
from .forms import UserRegisterForm, UserProfileForm
from .models import User, UserProfile, Role, Department, Designation
@jwt_or_session_required
@csrf_exempt
@permission_required('users.add_user')
def create_user(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "POST":
            user_form = UserRegisterForm(request.POST)
            profile_form = UserProfileForm(request.POST)

            errors = {}
            
            # VALIDATION FOR EMPLOYEE ID
            employee_id = request.POST.get('employee_id')
            if not employee_id or not employee_id.strip():
                errors['employee_id'] = ['Employee ID is required.']
            else:
                if UserProfile.objects.filter(employee_id=employee_id.strip()).exists():
                    errors['employee_id'] = ['Employee ID already exists. Please use a unique ID.']
            
            # PHONE VALIDATION
            phone = request.POST.get('phone', '').strip()
            if phone:
                if not re.match(r'^[6-9]\d{9}$', phone):
                    errors['phone'] = ['Phone number must be 10 digits and start with 6, 7, 8, or 9']
            
            # EMAIL VALIDATION
            email = request.POST.get('email', '').strip()
            if not email:
                errors['email'] = ['Email is required']
            elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                errors['email'] = ['Please enter a valid email address']
            
            # USERNAME VALIDATION
            username = request.POST.get('username', '').strip()
            if not username:
                errors['username'] = ['Username is required']
            elif len(username) < 3:
                errors['username'] = ['Username must be at least 3 characters long']
            
            # ✅ FIXED: ROLE VALIDATION - match the form field name 'role'
            role_id = request.POST.get('role')
            if not role_id:
                errors['role'] = ['Role is required']
            
            # FIRST NAME & LAST NAME VALIDATION
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            if not first_name:
                errors['first_name'] = ['First name is required']
            if not last_name:
                errors['last_name'] = ['Last name is required']
            
            # DEPARTMENT VALIDATION (REQUIRED)
            department_id = request.POST.get('department')
            if not department_id:
                errors['department'] = ['Department is required']
            
            # DESIGNATION VALIDATION (REQUIRED)
            designation_id = request.POST.get('designation')
            if not designation_id:
                errors['designation'] = ['Designation is required']
            
            # Validate forms
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
            
            # GENERATE RANDOM PASSWORD
            def generate_random_password(length=12):
                alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                password = ''.join(secrets.choice(alphabet) for i in range(length))
                return password
            
            random_password = generate_random_password()
            
            # Create user object
            user = user_form.save(commit=False)
            user.set_password(random_password)
            user.is_active = True
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.username = username
            
            # ✅ FIXED: Set role using role_id from 'role' field
            if role_id:
                try:
                    role_obj = Role.objects.get(id=role_id)
                    user.role_obj = role_obj
                    user.role = role_obj.name
                except Role.DoesNotExist:
                    pass
            
            # SEND EMAIL FIRST
            try:
                subject = 'Your Account Has Been Created - Login Credentials'
                html_message = render_to_string('activation_email.html', {
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
            
            # SAVE USER
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
                    'redirect_url': request.POST.get('redirect_url', '/admin_dashboard/'),
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
        
        # GET request - return form structure
        elif request.method == "GET":
            # Get all roles from Role model
            roles = Role.objects.all().values('id', 'name')
            departments = Department.objects.all().values('id', 'name')
            designations = Designation.objects.all().values('id', 'name')
            
            # User form fields structure - uses 'role_obj' to match POST
            user_fields = {
                'first_name': {'label': 'First Name', 'required': True, 'type': 'text', 'minlength': 2},
                'last_name': {'label': 'Last Name', 'required': True, 'type': 'text', 'minlength': 2},
                'email': {'label': 'Email', 'required': True, 'type': 'email', 'pattern': '[^@]+@[^@]+\\.[a-zA-Z]{2,}'},
                'username': {'label': 'Username', 'required': True, 'type': 'text', 'minlength': 3, 'pattern': '[A-Za-z0-9_]{3,}'},
                'role': {'label': 'Role', 'required': True, 'type': 'select', 'options': list(roles)},
            }
            
            # Profile form fields structure
            profile_fields = {
                'employee_id': {'label': 'Employee ID', 'required': True, 'type': 'text', 'minlength': 2},
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
    
    # Handle regular (non-AJAX) request
    return render(request, "create_user.html")

## delete user
from django.shortcuts import get_object_or_404
@jwt_or_session_required
@permission_required('users.delete_user')
def delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)

    # Prevent Admin from deleting themselves
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
        
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'User "{user_name}" deleted successfully!',
                'user_id': user_id
            })
        
        messages.success(request, f'User "{user_name}" deleted successfully!')
        return redirect("admin_dashboard")
    
    return redirect("admin_dashboard")


# Import Project and Task from their apps
from projects.models import Projects
from Tasks.forms import TaskForm 
## Assign Task
@jwt_or_session_required
@permission_required('Tasks.add_task')
@csrf_exempt
def assign_task(request):
    """Assign Task - AJAX enabled"""
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    default_redirect = dashboard_url_for(request.user)
    
    # Create form with filtered projects based on role
    class FilteredTaskForm(TaskForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if can_view_all_projects(request.user):
                self.fields['project'].queryset = Projects.objects.all()
            else:
                self.fields['project'].queryset = Projects.objects.filter(assigned_to=request.user)

                # 🔽 ADDED: Filter out admin users from assignee and observer fields
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
            
            self.fields['observers'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
            
            self.fields['assigned_by'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
    
    if request.method == "POST":
        form = FilteredTaskForm(request.POST)
        
        # Get dates for validation
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Validate dates - start must be before end
        if start_date and end_date:
            if start_date > end_date:
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': 'End date must be after start date',
                        'field': 'end_date'
                    }, status=400)
                else:
                    context = {
                        'form': form,
                        'date_error': "❌ End date must be after start date"
                    }
                    return render(request, "assign_task.html", context)
        
        if form.is_valid():
            # Step 1: Save the task instance but don't commit to DB yet
            task = form.save(commit=False)
            
            # Step 2: Get estimated time from the hidden field
            estimated_time = request.POST.get('estimated_time')
            if estimated_time:
                task.estimated_time = int(estimated_time)
            
            # Step 3: Get selected task owners
            assigned_by_ids = request.POST.getlist('assigned_by')
            
            # Step 4: Save the task to DB (need ID before setting ManyToMany)
            task.save()
            
            # Step 5: Set task owners - if none selected, use current user
            if assigned_by_ids:
                task.assigned_by.set(assigned_by_ids)
            else:
                # No owners selected, set current user as the owner
                task.assigned_by.set([request.user])
            
            # Step 6: Save other ManyToMany fields (assigned_to, observers)
            form.save_m2m()
            
            # Step 7: Create notifications for assigned employees
            from notifications.models import Notification
            for employee in task.assigned_to.all():
                if not Notification.objects.filter(
                    user=employee, 
                    message=f'Task "{task.name}" has been assigned to you'
                ).exists():
                    Notification.objects.create(
                        user=employee,
                        message=f'Task "{task.name}" has been assigned to you'
                    )
            
            # Step 8: Create notifications for observers
            assignee_names = ", ".join([u.get_full_name() or u.username for u in task.assigned_to.all()])
            for observer in task.observers.all():
                Notification.objects.create(
                    user=observer,
                    message=f'Task "{task.name}" has been assigned to {assignee_names}'
                )

            # Format estimated time for success message
            hours = task.estimated_time // 3600
            minutes = (task.estimated_time % 3600) // 60
            time_display = f"{hours} hour{'s' if hours != 1 else ''}"
            if minutes > 0:
                time_display += f" {minutes} minute{'s' if minutes != 1 else ''}"

            # AJAX response
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': f'Task "{task.name}" assigned successfully to {task.assigned_to.count()} employee(s)!',
                    'task_id': task.id,
                    'task_name': task.name,
                    'time_display': time_display,
                    'redirect_url': default_redirect,
                })
            else:
                # Regular form submission fallback
                messages.success(request, f'Task "{task.name}" assigned successfully to {task.assigned_to.count()} employee(s)!')
                return redirect(default_redirect)
        else:
            # Form is invalid
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
            else:
                context = {'form': form}
                return render(request, "assign_task.html", context)
    
    # GET request - show empty form
    else:
        form = FilteredTaskForm()

    return render(request, "assign_task.html", {"form": form})


## Create Project
from projects.forms import  ProjectResourceFormSet
from users.forms import ProjectForm
## Create Project
from notifications.models import Notification
from django.urls import reverse

@jwt_or_session_required
@permission_required('projects.add_projects')
@csrf_exempt
def create_project(request):
    # Helper function to get users based on capability
    def get_filtered_users(user):
        all_active_users = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True).order_by('first_name', 'username')
        if can_manage_users(user):
            return all_active_users

        manager_ids = [u.id for u in all_active_users if is_manager_like(u)]
        return all_active_users.exclude(id__in=manager_ids)
    
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "POST":
            # Get filtered users based on role
            filtered_users = get_filtered_users(request.user)
            
            class FilteredProjectForm(ProjectForm):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.fields['assigned_to'].queryset = filtered_users
            
            project_form = FilteredProjectForm(request.POST)
            resource_formset = ProjectResourceFormSet(request.POST, request.FILES)
            
            errors = {}
            
            # Get dates for validation
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            # Validate dates - start must be before end
            if start_date and end_date and start_date >= end_date:
                errors['date_error'] = ['End date must be after start date']
            
            # Validate forms
            if not project_form.is_valid():
                for field, error_list in project_form.errors.items():
                    errors[f'project_{field}'] = error_list
            
            if not resource_formset.is_valid():
                for form_index, form_errors in enumerate(resource_formset.errors):
                    if form_errors:
                        for field, error_list in form_errors.items():
                            errors[f'resource_{form_index}_{field}'] = error_list
            
            # If there are validation errors
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)
            
            # Forms are valid, proceed with project creation
            try:
                project = project_form.save(commit=False)
                project.created_by = request.user
                project.save()
                
                assigned_users = []
                if project_form.cleaned_data.get('assigned_to'):
                    assigned_users = list(project_form.cleaned_data['assigned_to'])
                    project.assigned_to.set(assigned_users)
                
                # Save resources
                resource_count = 0
                for resource_form in resource_formset:
                    if resource_form.cleaned_data and not resource_form.cleaned_data.get('DELETE', False):
                        resource = resource_form.save(commit=False)
                        resource.project = project
                        resource.save()
                        resource_count += 1
                
                # ✅ SEND NOTIFICATIONS TO ASSIGNED EMPLOYEES
                if assigned_users:
                    for user in assigned_users:
                        # Avoid duplicate notifications
                        if not Notification.objects.filter(
                            user=user,
                            message__icontains=f'project "{project.name}"'
                        ).exists():
                            Notification.objects.create(
                                user=user,
                                message=f'📁 You have been assigned to project "{project.name}" by {request.user.get_full_name() or request.user.username}.',
                                is_read=False
                            )
                
                # Determine redirect URL based on user role
                redirect_url = request.POST.get('redirect_url', '')
                if not redirect_url:
                    redirect_url = '/projects/' if can_view_all_projects(request.user) else dashboard_url_for(request.user)
                
                return JsonResponse({
                    'success': True,
                    'message': f'✅ Project "{project.name}" created successfully with {resource_count} resource(s)!',
                    'redirect_url': redirect_url,
                    'project': {
                        'id': project.id,
                        'name': project.name,
                        'description': project.description,
                        'status': project.status,
                        'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else None,
                        'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else None,
                        'assigned_to': [{
                            'id': user.id,
                            'name': user.get_full_name() or user.username,
                            'email': user.email
                        } for user in project.assigned_to.all()],
                        'resource_count': resource_count
                    }
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'errors': {
                        'system_error': [f'Error creating project: {str(e)}']
                    }
                }, status=500)
        
        # GET request - return form structure if needed
        elif request.method == "GET":
            filtered_users = get_filtered_users(request.user)
            
            class FilteredProjectForm(ProjectForm):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.fields['assigned_to'].queryset = filtered_users
            
            project_form = FilteredProjectForm()
            resource_formset = ProjectResourceFormSet()
            
            # Get field definitions for dynamic form rendering
            project_fields = {}
            for field_name, field in project_form.fields.items():
                project_fields[field_name] = {
                    'label': str(field.label),
                    'required': field.required,
                    'help_text': field.help_text,
                    'type': field.widget.__class__.__name__
                }
            
            # Render initial resource forms as HTML
            resource_forms_html = []
            for i, form in enumerate(resource_formset):
                resource_forms_html.append(render_to_string('partials/resource_form.html', {
                    'form': form,
                    'index': i
                }, request=request))
            
            return JsonResponse({
                'success': True,
                'project_fields': project_fields,
                'resource_forms_html': resource_forms_html,
                'total_forms': len(resource_formset)
            })
    
    # Handle regular (non-AJAX) request
    if request.method == "POST":
        filtered_users = get_filtered_users(request.user)
        
        class FilteredProjectForm(ProjectForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields['assigned_to'].queryset = filtered_users
        
        project_form = FilteredProjectForm(request.POST)
        resource_formset = ProjectResourceFormSet(request.POST, request.FILES)
        
        # Get dates for validation
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Validate dates - start must be before end
        if start_date and end_date:
            if start_date >= end_date:
                context = {
                    "form": project_form,
                    "resource_formset": resource_formset,
                    "date_error": "❌ End date must be after start date"
                }
                return render(request, "create_project.html", context)

        if project_form.is_valid() and resource_formset.is_valid():
            project = project_form.save(commit=False)
            project.created_by = request.user
            project.save()
            
            assigned_users = []
            if project_form.cleaned_data.get('assigned_to'):
                assigned_users = list(project_form.cleaned_data['assigned_to'])
                project.assigned_to.set(assigned_users)
            
            for resource_form in resource_formset:
                if resource_form.cleaned_data and not resource_form.cleaned_data.get('DELETE', False):
                    resource = resource_form.save(commit=False)
                    resource.project = project
                    resource.save()
            
            # ✅ SEND NOTIFICATIONS TO ASSIGNED EMPLOYEES (Regular POST)
            if assigned_users:
                for user in assigned_users:
                    # Avoid duplicate notifications
                    if not Notification.objects.filter(
                        user=user,
                        message__icontains=f'project "{project.name}"'
                    ).exists():
                        Notification.objects.create(
                            user=user,
                            message=f'📁 You have been assigned to project "{project.name}" by {request.user.get_full_name() or request.user.username}.',
                            is_read=False
                        )

            messages.success(request, "✅ Project created successfully!")
            if can_view_all_projects(request.user):
                return redirect("view_projects")
            return redirect(dashboard_url_for(request.user))
        
        else:
            # Form is invalid - show errors
            if not project_form.is_valid():
                for field, errors in project_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
            
            if not resource_formset.is_valid():
                messages.error(request, "Please check the resources section")
            
            context = {
                "form": project_form,
                "resource_formset": resource_formset
            }
            return render(request, "create_project.html", context)
    
    # GET request - show empty form
    else:
        filtered_users = get_filtered_users(request.user)
        
        class FilteredProjectForm(ProjectForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields['assigned_to'].queryset = filtered_users
        
        project_form = FilteredProjectForm()
        resource_formset = ProjectResourceFormSet()

    context = {
        "form": project_form,
        "resource_formset": resource_formset
    }
    return render(request, "create_project.html", context)


## task_dashboard
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
@jwt_or_session_required
@permission_required('Tasks.view_task')
def task_dashboard(request):
    """Task dashboard showing all tasks in list view"""
    
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get pagination parameters
        page = request.GET.get("page", 1)
        page_size = request.GET.get("page_size", 10)
        
        if has_any(request.user, ['Tasks.view_all_tasks', 'tasks.view_all_tasks']):
            tasks = Task.objects.all().order_by('-created_at')
        elif can_manage_users(request.user):
            # Admin gets all tasks
            tasks = Task.objects.all().order_by('-created_at')
        elif can_manage_projects(request.user):
            # Team leads / Managers can view tasks from their projects
            my_projects = Projects.objects.filter(assigned_to=request.user)
            my_project_ids = my_projects.values_list('id', flat=True)
            
            # They also see tasks explicitly assigned to them in other projects
            tasks = Task.objects.filter(
                models.Q(project_id__in=my_project_ids) | 
                models.Q(assigned_to=request.user)
            ).distinct().order_by('-created_at')
        else:
            # Regular employee / contributor explicitly only sees tasks assigned to them
            tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')
        
        # Statistics (using full queryset for stats)
        total_tasks = tasks.count()
        ongoing_count = tasks.filter(status='ONGOING').count()
        completed_count = tasks.filter(status='COMPLETED').count()
        overdue_count = 0  # Will calculate after pagination
        
        # Apply pagination
        paginator = Paginator(tasks, page_size)
        try:
            tasks_page = paginator.page(page)
        except PageNotAnInteger:
            tasks_page = paginator.page(1)
        except EmptyPage:
            tasks_page = paginator.page(paginator.num_pages)
        
        # Calculate overdue count and send notifications for paginated tasks
        now = timezone.now()
        
        tasks_data = []
        for task in tasks_page:
            # Calculate current time spent
            if task.status == 'ONGOING' and task.start_time:
                elapsed = now - task.start_time
                if task.total_paused_duration:
                    elapsed = elapsed - task.total_paused_duration
                current_seconds = int(elapsed.total_seconds())
            elif task.status == 'COMPLETED' and task.total_time:
                current_seconds = int(task.total_time.total_seconds())
            else:
                current_seconds = 0
            
            # Format time spent display
            hours = current_seconds // 3600
            minutes = (current_seconds % 3600) // 60
            seconds = current_seconds % 60
            time_spent_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # Format estimated time display
            if task.estimated_time:
                est_hours = task.estimated_time // 3600
                est_minutes = (task.estimated_time % 3600) // 60
                estimated_display = f"{est_hours:02d}:{est_minutes:02d}:00"
            else:
                estimated_display = "04:00:00"
            
            # Check if task is overdue
            is_overdue = False
            if task.status != 'COMPLETED' and task.estimated_time:
                if current_seconds > task.estimated_time:
                    is_overdue = True
                    overdue_count += 1
            
            # Get assignees
            assignees_list = []
            for assignee in task.assigned_to.all()[:2]:
                assignees_list.append(assignee.get_full_name() or assignee.username)
            
            tasks_data.append({
                'id': task.id,
                'name': task.name,
                'status': task.status,
                'status_display': task.get_status_display(),
                'time_spent_display': time_spent_display,
                'estimated_display': estimated_display,
                'is_overdue': is_overdue,
                'deadline': task.deadline.strftime('%b %d, %H:%M') if task.deadline else None,
                'project_name': task.project.name[:15] if task.project.name else 'N/A',
                'assignees': assignees_list,
                'total_assignees': task.assigned_to.count(),
                'view_url': f"/employee/tasks/?task_id={task.id}"
            })
        
        return JsonResponse({
            'success': True,
            'tasks': tasks_data,
            'total_tasks': total_tasks,
            'ongoing_count': ongoing_count,
            'completed_count': completed_count,
            'overdue_count': overdue_count,
            'total_pages': paginator.num_pages,
            'current_page': tasks_page.number,
            'has_previous': tasks_page.has_previous(),
            'has_next': tasks_page.has_next(),
            'previous_page_number': tasks_page.previous_page_number() if tasks_page.has_previous() else None,
            'next_page_number': tasks_page.next_page_number() if tasks_page.has_next() else None,
            'page_size': int(page_size)
        })
    
    # Regular request - return full template with data
    if has_any(request.user, ['Tasks.view_all_tasks', 'tasks.view_all_tasks']):
        tasks = Task.objects.all().order_by('-created_at')
    elif can_manage_users(request.user):
        tasks = Task.objects.all().order_by('-created_at')
    elif can_manage_projects(request.user):
        my_projects = Projects.objects.filter(assigned_to=request.user)
        my_project_ids = my_projects.values_list('id', flat=True)
        tasks = Task.objects.filter(
            models.Q(project_id__in=my_project_ids) | 
            models.Q(assigned_to=request.user)
        ).distinct().order_by('-created_at')
    else:
        tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')

    # Statistics
    total_tasks = tasks.count()
    ongoing_count = tasks.filter(status='ONGOING').count()
    completed_count = tasks.filter(status='COMPLETED').count()

    # Add pagination for regular request
    paginator = Paginator(tasks, 10)
    page = request.GET.get('page', 1)
    try:
        tasks_page = paginator.page(page)
    except PageNotAnInteger:
        tasks_page = paginator.page(1)
    except EmptyPage:
        tasks_page = paginator.page(paginator.num_pages)

    # Calculate overdue count for paginated tasks
    now = timezone.now()
    overdue_count = 0
    from notifications.models import Notification

    for task in tasks_page:
        # Calculate current time spent
        if task.status == 'ONGOING' and task.start_time:
            elapsed = now - task.start_time
            if task.total_paused_duration:
                elapsed = elapsed - task.total_paused_duration
            current_seconds = int(elapsed.total_seconds())
        elif task.status == 'COMPLETED' and task.total_time:
            current_seconds = int(task.total_time.total_seconds())
        else:
            current_seconds = 0
        
        # Format time spent display
        hours = current_seconds // 3600
        minutes = (current_seconds % 3600) // 60
        seconds = current_seconds % 60
        task.time_spent_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Format estimated time display
        if task.estimated_time:
            est_hours = task.estimated_time // 3600
            est_minutes = (task.estimated_time % 3600) // 60
            task.estimated_display = f"{est_hours:02d}:{est_minutes:02d}:00"
        else:
            task.estimated_display = "04:00:00"
        
        # Check if task is overdue
        if task.status != 'COMPLETED' and task.estimated_time:
            if current_seconds > task.estimated_time:
                task.is_overdue = True
                overdue_count += 1
                
                # 🔔 SEND NOTIFICATIONS FOR OVERDUE TASK
                for owner in task.assigned_by.all():
                    existing = Notification.objects.filter(
                        user=owner,
                        message__icontains=f"Task '{task.name}' is overdue",
                        created_at__date=now.date()
                    ).exists()
                    
                    if not existing:
                        Notification.objects.create(
                            user=owner,
                            message=f"⚠️ Task '{task.name}' (Project: {task.project.name}) is overdue!",
                            is_read=False
                        )
                
                for assignee in task.assigned_to.all():
                    existing = Notification.objects.filter(
                        user=assignee,
                        message__icontains=f"Task '{task.name}'",
                        created_at__date=now.date()
                    ).exists()
                    
                    if not existing:
                        Notification.objects.create(
                            user=assignee,
                            message=f"⚠️ Task '{task.name}' assigned to you is overdue!",
                            is_read=False
                        )
                
                for observer in task.observers.all():
                    existing = Notification.objects.filter(
                        user=observer,
                        message__icontains=f"Task '{task.name}'",
                        created_at__date=now.date()
                    ).exists()
                    
                    if not existing:
                        Notification.objects.create(
                            user=observer,
                            message=f"⚠️ Task '{task.name}' (Project: {task.project.name}) is overdue!",
                            is_read=False
                        )
                
                print(f"🔔 Overdue notifications sent for task: {task.name}")
            else:
                task.is_overdue = False
        else:
            task.is_overdue = False

    context = {
        'tasks': tasks_page,
        'total_tasks': total_tasks,
        'ongoing_count': ongoing_count,
        'completed_count': completed_count,
        'overdue_count': overdue_count,
        'now': now,
        'paginator': paginator,
        'page_obj': tasks_page,
    }
    return render(request, 'task_dashboard.html', context)



## TaskSummary 
from django.http import JsonResponse
@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def add_task_summary(request, task_id):
    """Add summary to a task - AJAX enabled"""
    
    try:
        if can_manage_all_tasks(request.user):
            task = get_object_or_404(Task, id=task_id)
        else:
            task = get_object_or_404(Task, id=task_id, assigned_to=request.user)
    except:
        return JsonResponse({
            'success': False,
            'error': 'Task not found'
        }, status=404)
    
    # Check if task is in correct state
    if task.status != "ONGOING":
        return JsonResponse({
            'success': False,
            'error': 'You can only add summary to ongoing tasks.'
        }, status=400)
    
    if request.method == 'POST':
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                data = json.loads(request.body)
                summary = data.get('summary', '').strip()
            except:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON'
                }, status=400)
        else:
            # Regular form submission (fallback)
            summary = request.POST.get('summary', '').strip()
        
        if not summary:
            return JsonResponse({
                'success': False,
                'errors': {
                    'summary': ['Please enter a valid summary.']
                }
            }, status=400)
        
        task.summary = summary
        task.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Summary added successfully!',
            'task_id': task.id
        })
    
    # GET request - render template
    return render(request, 'add_task_summary.html', {'task': task})



import math
## employee task
import math
## employee task
@jwt_or_session_required
@permission_required('Tasks.view_task')
def employee_tasks(request):
    task_id = request.GET.get('task_id')
    employee_id = request.GET.get('employee_id')
    
    # Helper function to check view_all_tasks permission
    def has_view_all_tasks(user):
        return has_any(user, ['Tasks.view_all_tasks', 'tasks.view_all_tasks'])
    
    # Handle AJAX request - return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Case 1: Manager viewing specific employee's tasks
        if employee_id and is_manager_like(request.user):
            employee = get_object_or_404(User, id=employee_id)
            tasks = Task.objects.filter(assigned_to=employee).order_by('-created_at')
            
            tasks_data = []
            for task in tasks:
                tasks_data.append({
                    'id': task.id,
                    'name': task.name,
                    'status': task.status,
                    'status_display': task.get_status_display(),
                })
            
            return JsonResponse({
                'success': True,
                'tasks': tasks_data,
                'viewing_employee': employee.get_full_name() or employee.username,
                'total_tasks': len(tasks_data)
            })
        
        # Case 2: Viewing single task by ID - FIXED PERMISSION CHECK
        elif task_id:
            task = get_object_or_404(Task, id=task_id)
            
            # Check permission: view_all_tasks OR assigned to task OR can_manage_all_tasks
            if not (has_view_all_tasks(request.user) or task.assigned_to.filter(id=request.user.id).exists() or can_manage_all_tasks(request.user)):
                return JsonResponse({
                    'success': False, 
                    'error': "You don't have permission to view this task."
                }, status=403)
            
            return JsonResponse({
                'success': True,
                'task': {
                    'id': task.id,
                    'name': task.name,
                    'description': task.description,
                    'status': task.status,
                    'status_display': task.get_status_display(),
                    'summary': task.summary,
                }
            })
        
        # Case 3: Employee viewing their own tasks list
        else:
            tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')
            tasks_data = [{'id': t.id, 'name': t.name, 'status': t.status, 'status_display': t.get_status_display()} for t in tasks]
            return JsonResponse({'success': True, 'tasks': tasks_data, 'total_tasks': len(tasks_data)})
    
    # ========== YOUR ORIGINAL CODE BELOW - COMPLETELY UNCHANGED ==========
    # Case 1: Manager viewing specific employee's tasks
    if employee_id and is_manager_like(request.user):
        employee = get_object_or_404(User, id=employee_id)
        tasks = Task.objects.filter(assigned_to=employee).order_by('-created_at')
        
        # Add calculated fields for each task
        for task in tasks:
            if task.estimated_time:
                hours = task.estimated_time // 3600
                minutes = (task.estimated_time % 3600) // 60
                task.estimated_display = f"{hours:02d}:{minutes:02d}:00"
            else:
                task.estimated_display = "01:00:00"
            
            if task.status == "ONGOING" and task.start_time:
                elapsed = timezone.now() - task.start_time
                if task.total_paused_duration:
                    elapsed = elapsed - task.total_paused_duration
                if task.paused_time:
                    current_pause = timezone.now() - task.paused_time
                    elapsed = elapsed - current_pause
                
                total_seconds = int(elapsed.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                task.current_display_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            elif task.status == "COMPLETED" and task.total_time:
                total_seconds = int(task.total_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                task.total_time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        return render(request, "employee_tasks.html", {
            'tasks': tasks,
            'current_time': timezone.now(),
            'viewing_employee': employee
        })
    
    # Case 2: Viewing single task by ID - FIXED PERMISSION CHECK
    elif task_id:
        task = get_object_or_404(Task, id=task_id)
        
        # Check permission: view_all_tasks OR assigned to task OR can_manage_all_tasks
        if not (has_view_all_tasks(request.user) or task.assigned_to.filter(id=request.user.id).exists() or can_manage_all_tasks(request.user)):
            messages.error(request, "You don't have permission to view this task.")
            return redirect('task_dashboard')
        
        tasks = [task]
        
        # Format estimated time for display
        if task.estimated_time:
            hours = task.estimated_time // 3600
            minutes = (task.estimated_time % 3600) // 60
            task.estimated_display = f"{hours:02d}:{minutes:02d}:00"
        else:
            task.estimated_display = "01:00:00"
        
        # Calculate current time for ongoing tasks
        if task.status == "ONGOING" and task.start_time:
            elapsed = timezone.now() - task.start_time
            if task.total_paused_duration:
                elapsed = elapsed - task.total_paused_duration
            if task.paused_time:
                current_pause = timezone.now() - task.paused_time
                elapsed = elapsed - current_pause
            
            total_seconds = int(elapsed.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            task.current_display_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Format completed task time
        elif task.status == "COMPLETED" and task.total_time:
            total_seconds = int(task.total_time.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            task.total_time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # Case 3: Employee viewing their own tasks list
    else:
        tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')
        for task in tasks:
            if task.estimated_time:
                hours = task.estimated_time // 3600
                minutes = (task.estimated_time % 3600) // 60
                task.estimated_display = f"{hours:02d}:{minutes:02d}:00"
    
    return render(request, "employee_tasks.html", {
        'tasks': tasks,
        'current_time': timezone.now()
    })

## update task status
# @jwt_or_session_required
# @allowed_roles(allowed_roles=["EMPLOYEE"])
# def update_task_status(request, task_id):

#     task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

#     if request.method == "POST":
#         new_status = request.POST.get("status")

#         # Workflow control
#         if task.status == "PENDING" and new_status == "ONGOING":
#             task.status = "ONGOING"
#             task.save()

#         elif task.status == "ONGOING" and new_status == "COMPLETED":
#             task.status = "COMPLETED"
#             task.save()

#         return redirect("employee_tasks")

#     return render(request, "update_task_status.html", {
#         "task": task,
#         "status_choices": Task.STATUS_CHOICES
#     })


## start task
from django.utils import timezone
from django.urls import reverse
import datetime
## START TASK - AJAX VERSION
@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def start_task(request, task_id):
    """Start a task - AJAX enabled"""
    
    if can_manage_all_tasks(request.user):
        task = get_object_or_404(Task, id=task_id)
    else:
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    # Check if task can be started
    if task.status != "PENDING":
        return JsonResponse({
            'success': False,
            'error': f'Task cannot be started because it is {task.get_status_display()}.'
        }, status=400)

    # Reset the task for fresh start
    task.status = "ONGOING"
    task.start_time = timezone.now()
    task.paused_time = None
    task.total_paused_duration = datetime.timedelta()
    task.total_time = None
    task.end_time = None
    
    task.save(update_fields=[
        'status', 'start_time', 'paused_time', 
        'total_paused_duration', 'total_time', 'end_time'
    ])
    if task.project and task.project.created_by:
        Notification.objects.create(
            user=task.project.created_by,
            message=f"▶️ Task '{task.name}' has been started by {request.user.get_full_name() or request.user.username}"
        )
        
    return JsonResponse({
        'success': True,
        'message': f'Task "{task.name}" started successfully!',
        'task_id': task.id,
        'status': 'ONGOING',
        'start_time': task.start_time.isoformat()
    })


## PAUSE TASK - AJAX VERSION
@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def pause_task(request, task_id):
    """Pause an ongoing task - AJAX enabled"""
    
    if can_manage_all_tasks(request.user):
        task = get_object_or_404(Task, id=task_id)
    else:
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    # Check if task can be paused
    if task.status != "ONGOING":
        return JsonResponse({
            'success': False,
            'error': 'Only ongoing tasks can be paused.'
        }, status=400)

    # Check if task is already paused
    if task.paused_time is not None:
        return JsonResponse({
            'success': False,
            'error': 'Task is already paused.'
        }, status=400)

    # Pause the task
    task.paused_time = timezone.now()
    task.save()
    if task.project and task.project.created_by:
        Notification.objects.create(
            user=task.project.created_by,
            message=f"⏸️ Task '{task.name}' has been paused by {request.user.get_full_name() or request.user.username}"
        )

    return JsonResponse({
        'success': True,
        'message': f'Task "{task.name}" paused.',
        'task_id': task.id,
        'paused_time': task.paused_time.isoformat()
    })


## RESUME TASK - AJAX VERSION
@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def resume_task(request, task_id):
    """Resume a paused task - AJAX enabled"""
    
    if can_manage_all_tasks(request.user):
        task = get_object_or_404(Task, id=task_id)
    else:
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    # Check if task is paused
    if task.status != "ONGOING" or task.paused_time is None:
        return JsonResponse({
            'success': False,
            'error': 'Task is not paused.'
        }, status=400)

    # Calculate paused duration
    paused_duration = timezone.now() - task.paused_time

    # Add to total paused duration
    if task.total_paused_duration:
        task.total_paused_duration += paused_duration
    else:
        task.total_paused_duration = paused_duration

    # Clear paused time
    task.paused_time = None
    task.save()
    if task.project and task.project.created_by:
        Notification.objects.create(
            user=task.project.created_by,
            message=f"⏸️ Task '{task.name}' has been paused by {request.user.get_full_name() or request.user.username}"
        )

    return JsonResponse({
        'success': True,
        'message': f'Task "{task.name}" resumed.',
        'task_id': task.id
    })


## COMPLETE TASK - AJAX VERSION
@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def complete_task(request, task_id):
    """Complete a task - AJAX enabled with JSON response"""
    
    if can_manage_all_tasks(request.user):
        task = get_object_or_404(Task, id=task_id)
    else:
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    # Check if task can be completed
    if task.status == "COMPLETED":
        return JsonResponse({
            'success': False,
            'error': 'Task is already completed.'
        }, status=400)

    # IMPORTANT: Check if summary exists
    if not task.summary:
        return JsonResponse({
            'success': False,
            'error': 'Please add a task summary before completing.',
            'redirect_url': reverse('add_task_summary', args=[task.id])
        }, status=400)

    # If task is ongoing, calculate final time
    if task.status == "ONGOING" and task.start_time:
        # If task is paused, add that pause duration first
        if task.paused_time:
            paused_duration = timezone.now() - task.paused_time
            if task.total_paused_duration:
                task.total_paused_duration += paused_duration
            else:
                task.total_paused_duration = paused_duration
            task.paused_time = None

        # Calculate total time spent
        total_spent = timezone.now() - task.start_time

        # Subtract paused time
        if task.total_paused_duration:
            total_spent = total_spent - task.total_paused_duration

        task.total_time = total_spent
        task.end_time = timezone.now()

    # Mark as completed
    task.status = "COMPLETED"
    task.save()

    # Format time for display
    time_display = "00:00:00"
    if task.total_time:
        total_seconds = int(task.total_time.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # ✅ UPDATED: Notify managers, admins, and project creator
    employee_name = request.user.get_full_name() or request.user.username
    message = f"✅ Task '{task.name}' has been completed by {employee_name}. Time spent: {time_display}"
    
    # Get all users to notify (managers + admins + project creator)
    users_to_notify = set()
    
    # Add managers (users with manager-like permissions)
    for user in User.objects.filter(is_active=True):
        if is_manager_like(user):
            users_to_notify.add(user)
    
    # Add admins
    for admin in User.objects.filter(role='ADMIN', is_active=True):
        users_to_notify.add(admin)
    
    # Add project creator if not already included
    if task.project and task.project.created_by:
        users_to_notify.add(task.project.created_by)
    
    # Create notifications for all users
    for user in users_to_notify:
        Notification.objects.create(user=user, message=message)

    # Return JSON response instead of redirect
    return JsonResponse({
        'success': True,
        'message': f'Task "{task.name}" completed! Total time: {time_display}',
        'task_id': task.id,
        'time_display': time_display,
        'status': 'COMPLETED'
    })


from .models import Department, Designation
from .forms import UserProfileForm

# ================== Departments ==================
# List all departments
@jwt_or_session_required
@permission_required(['users.view_department', 'users.add_department', 'users.change_department', 'users.delete_department'])
def departments(request):
    departments = Department.objects.all()

    # Handle creation of a new department via normal form POST
    if request.method == "POST":
        new_dept_name = request.POST.get("department_name")
        if new_dept_name:
            Department.objects.create(name=new_dept_name)
            messages.success(request, f"Department '{new_dept_name}' created successfully!")
            return redirect("departments")

    # Handle AJAX request
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        dept_list = [{"id": dept.id, "name": dept.name} for dept in departments]
        return JsonResponse({"departments": dept_list})

    # Normal page render
    return render(request, "department_list.html", {"departments": departments})


## Create departments
from django.http import JsonResponse

@jwt_or_session_required
@permission_required('users.add_department')
@csrf_exempt
def create_department(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            department = Department.objects.create(name=name)
            
            # Check if it's an AJAX request - Updated for Django 4.0+
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
    
    return render(request, "create_department.html", {"action": "Create"})


# Show all users in a department
@jwt_or_session_required
@permission_required(['users.view_department', 'users.add_department', 'users.change_department', 'users.delete_department'])
def department_detail(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    users_in_dept = User.objects.filter(profile__department=department)

    # AJAX response
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
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

    # Normal page render
    return render(request, "department_detail.html", {
        "department": department,
        "users": users_in_dept
    })


## delete_department
@jwt_or_session_required
@permission_required('users.delete_department')
@csrf_exempt
def delete_department(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    dept_name = department.name
    
    if request.method == "POST":
        department.delete()
        
        # Check if it's an AJAX request - Updated for Django 4.0+
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "message": f"Department '{dept_name}' deleted successfully!",
                "dept_id": dept_id
            })
        
        messages.success(request, "Department deleted successfully!")
        return redirect("departments")
    
    return redirect("departments")

# <!--Designation-->
# List all designations
@jwt_or_session_required
@permission_required(['users.view_designation', 'users.add_designation', 'users.change_designation', 'users.delete_designation'])
def designations(request):
    designations = Designation.objects.all()
    
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        designations_list = [
            {
                "id": desig.id,
                "name": desig.name,
                "user_count": User.objects.filter(profile__designation=desig).count()
            }
            for desig in designations
        ]
        return JsonResponse({
            "success": True,
            "designations": designations_list
        })
    
    return render(request, "designation_list.html", {"designations": designations})



@jwt_or_session_required
@permission_required('users.add_designation')
@csrf_exempt
def create_designation(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            designation = Designation.objects.create(name=name)
            
            # Check if it's an AJAX request
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
    
    return render(request, "designation_form.html", {"action": "Create"})



# Show all users in a designation
@jwt_or_session_required
@permission_required(['users.view_designation', 'users.add_designation', 'users.change_designation', 'users.delete_designation'])
def designation_detail(request, desig_id):
    designation = get_object_or_404(Designation, id=desig_id)
    users_in_desig = User.objects.filter(profile__designation=designation)
    
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
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
    
    return render(request, "designation_detail.html", {
        "designation": designation,
        "users": users_in_desig
    })


## delete designation
@jwt_or_session_required
@permission_required('users.delete_designation')
@csrf_exempt
def delete_designation(request, desig_id):
    desig = get_object_or_404(Designation, id=desig_id)
    desig_name = desig.name
    
    if request.method == "POST":
        desig.delete()
        
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "message": f"Designation '{desig_name}' deleted successfully!",
                "desig_id": desig_id
            })
        
        messages.success(request, "Designation deleted successfully!")
        return redirect("designations")
    
    return redirect("designations")


## Edit User
# def edit_user(request,user_id):
#     user = get_object_or_404(User,id=user_id)

#     if request.method == "POST":
#         user.email = request.POST.get("email")
#         user.username = request.POST.get("username")
#         user.role = request.POST.get("role")
#         user.save()

#         messages.success(request,"user updated successfully")
#         return redirect("admin_dashboard")
    
#     return render(request,"edit_user.html",{"user":user})


## User Analytics
@jwt_or_session_required
@permission_required(['Tasks.view_task', 'users.view_user', 'users.add_user', 'users.change_user', 'users.delete_user', 'Tasks.add_task'])
@csrf_exempt
def user_analytics(request):

     # Check if user has either view_task or view_user permission
    if not (request.user.has_perm('Tasks.view_task') or request.user.has_perm('users.view_user')):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False, 
                'error': 'You do not have permission to view analytics'
            }, status=403)
        return redirect('dashboard')

    scoped_manager_mode = can_add_task(request.user) and not can_manage_users(request.user)
    full_scope_mode = can_manage_users(request.user)
    
    # ========== Get users based on capability ==========
        # ========== Get users based on capability ==========
    if scoped_manager_mode:
        # TEAM_LEAD sees only employees in their projects
        my_projects = Projects.objects.filter(assigned_to=request.user)
        my_project_ids = my_projects.values_list('id', flat=True)
        contributor_ids = set(_contributor_user_ids())
        
        tasks_in_my_projects = Task.objects.filter(project_id__in=my_project_ids)
        task_assignee_ids = set(tasks_in_my_projects.values_list('assigned_to', flat=True).distinct())
        
        project_member_ids = set(User.objects.filter(
            projects__in=my_projects,
        ).values_list('id', flat=True).distinct())
        
        all_contributor_ids = (task_assignee_ids | project_member_ids) & contributor_ids
        users = User.objects.filter(id__in=all_contributor_ids).order_by('username')
        
        users = users | User.objects.filter(id=request.user.id)
    elif full_scope_mode:
        # ADMIN sees all users
        users = User.objects.all().order_by('username')
    elif can_view_user(request.user) and not can_add_task(request.user) and not can_manage_users(request.user):
        # Project Coordinator (has view_user only) - sees EMPLOYEES and TEAM_LEADS only (not ADMIN)
        users = User.objects.filter(
            is_active=True
        ).exclude(
            is_staff=True
        ).exclude(
            is_superuser=True
        ).exclude(
            role='ADMIN'
        ).order_by('username')
    else:
        # Regular employee sees only themselves
        users = User.objects.filter(id=request.user.id)
    
    selected_user_id = request.GET.get('user_id')
    selected_user = None
    
    # Check if requesting top performers
    get_top_performers = request.GET.get('get_top_performers') == 'true'
    
    if get_top_performers:
        # Calculate top performers for users visible to this capability scope
        if scoped_manager_mode:
            my_projects = Projects.objects.filter(assigned_to=request.user)
            my_project_ids = my_projects.values_list('id', flat=True)
            contributor_ids = set(_contributor_user_ids())
            
            tasks_in_my_projects = Task.objects.filter(project_id__in=my_project_ids)
            task_assignee_ids = set(tasks_in_my_projects.values_list('assigned_to', flat=True).distinct())
            
            project_member_ids = set(User.objects.filter(
                projects__in=my_projects,
            ).values_list('id', flat=True).distinct())
            
            visible_user_ids = (task_assignee_ids | project_member_ids) & contributor_ids
            all_users = User.objects.filter(id__in=visible_user_ids)
        elif full_scope_mode:
            all_users = User.objects.filter(is_active=True)
        else:
            all_users = User.objects.filter(id=request.user.id)
        
        top_performers = []
        
        for user in all_users:
            if scoped_manager_mode:
                tasks = Task.objects.filter(
                    assigned_to=user,
                    project_id__in=my_project_ids
                )
            else:
                tasks = Task.objects.filter(assigned_to=user)
            
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(status='COMPLETED').count()
            
            if total_tasks > 0:
                performance_score = int((completed_tasks / total_tasks) * 100)
            else:
                performance_score = 0
            
            # Only include users who have at least 1 task
            if total_tasks > 0:
                top_performers.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'role_display': user.role,
                    'total_tasks': total_tasks,
                    'completed_tasks': completed_tasks,
                    'performance_score': performance_score
                })
        
        # Sort by performance score (highest first)
        top_performers.sort(key=lambda x: x['performance_score'], reverse=True)
        
        return JsonResponse({
            'success': True,
            'top_performers': top_performers
        })
    
    # Regular analytics logic
    if selected_user_id:
        selected_user = get_object_or_404(User, id=selected_user_id)
        
        # Scoped managers can only view self + their contributor users.
        if scoped_manager_mode:
            visible_ids = set(users.values_list('id', flat=True))
            if selected_user.id not in visible_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'You do not have permission to view this user\'s analytics'
                }, status=403)
        
        if scoped_manager_mode:
            my_projects = Projects.objects.filter(assigned_to=request.user)
            my_project_ids = my_projects.values_list('id', flat=True)
            
            tasks = Task.objects.filter(
                assigned_to=selected_user,
                project_id__in=my_project_ids
            )
            projects = Projects.objects.filter(
                assigned_to=selected_user,
                id__in=my_project_ids
            )
        elif full_scope_mode:
            tasks = Task.objects.filter(assigned_to=selected_user)
            projects = Projects.objects.filter(assigned_to=selected_user)
        else:
            if selected_user.id != request.user.id:
                return JsonResponse({
                    'success': False,
                    'error': 'You do not have permission to view this user\'s analytics'
                }, status=403)
            tasks = Task.objects.filter(assigned_to=request.user)
            projects = Projects.objects.filter(assigned_to=request.user)
    else:
        if scoped_manager_mode:
            my_projects = Projects.objects.filter(assigned_to=request.user)
            my_project_ids = my_projects.values_list('id', flat=True)
            
            tasks = Task.objects.filter(project_id__in=my_project_ids)
            projects = Projects.objects.filter(id__in=my_project_ids)
        elif full_scope_mode:
            tasks = Task.objects.all()
            projects = Projects.objects.all()
        else:
            tasks = Task.objects.filter(assigned_to=request.user)
            projects = Projects.objects.filter(assigned_to=request.user)

    total_tasks = tasks.count()
    completed = tasks.filter(status='COMPLETED').count()
    ongoing = tasks.filter(status='ONGOING').count()
    pending = tasks.filter(status='PENDING').count()
    overdue = tasks.filter(deadline__lt=timezone.now()).exclude(status='COMPLETED').count()
    performance = int((completed / total_tasks) * 100) if total_tasks > 0 else 0
    stroke_offset = 283 - (performance * 2.83)
    last_7_days = timezone.now() - timedelta(days=7)
    recent_completed = tasks.filter(status='COMPLETED', end_time__gte=last_7_days).count()
    avg_time = tasks.filter(total_time__isnull=False).aggregate(avg=Avg('total_time'))['avg']

    def format_duration(duration):
        if not duration:
            return "00:00:00"
        total_seconds = int(duration.total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    avg_time_formatted = format_duration(avg_time)
    projects_count = projects.count()
    remaining = total_tasks - completed

    cards = [
        {"label": "Total", "value": total_tasks, "color": "gray"},
        {"label": "Completed", "value": completed, "color": "green"},
        {"label": "Ongoing", "value": ongoing, "color": "blue"},
        {"label": "Pending", "value": pending, "color": "yellow"},
        {"label": "Overdue", "value": overdue, "color": "red"},
        {"label": "Projects", "value": projects_count, "color": "gray"},
    ]

    analytics = {
        'total': total_tasks,
        'completed': completed,
        'ongoing': ongoing,
        'pending': pending,
        'overdue': overdue,
        'projects': projects_count,
        'performance': performance,
        'stroke_offset': stroke_offset,
        'recent_completed': recent_completed,
        'avg_time': avg_time_formatted,
        'remaining': remaining,
        'cards': cards,
    }

    # Return JSON if AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        users_list = []
        for user in users:
            users_list.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'full_name': user.get_full_name() or user.username
            })
        
        selected_user_name = None
        if selected_user:
            selected_user_name = selected_user.username
        elif not selected_user and not full_scope_mode:
            selected_user_name = 'My Performance'
        else:
            selected_user_name = 'All Users'
        
        return JsonResponse({
            'success': True,
            'analytics': analytics,
            'selected_user': selected_user_name,
            'selected_user_id': selected_user.id if selected_user else None,
            'users': users_list
        })

    # Normal page render
    return render(request, 'user_analytics.html', {
        'users': users,
        'selected_user': selected_user,
        'analytics': analytics
    })

## home page

def home(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get token from cookie or header
        token = None
        
        # Try to get from cookie first
        auth_cookie = request.COOKIES.get('access_token')
        if auth_cookie:
            token = auth_cookie
        
        # If not in cookie, try Authorization header
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        user_data = None
        if token:
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                from users.models import User
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
    # Regular request - return template
    return render(request, "home.html")


## Check email exists
from django.views.decorators.http import require_http_methods
import json

@csrf_exempt
@require_http_methods(["POST"])
def check_email_exists(request):
    """Check if email is registered in the system - Public endpoint"""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({'exists': False, 'error': 'Email is required'}, status=400)
        
        # Check if user exists with this email
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
        # Only allow image upload, nothing else
        profile.profile_image = request.FILES['profile_image']
        profile.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Profile picture updated successfully!',
                'image_url': profile.profile_image.url if profile.profile_image else None
            })
    
    # For GET request - return template with user data
    return render(request, 'my_profile.html', {
        'user': user,
        'profile': profile
    })

## Permission Management Views
@jwt_or_session_required
@permission_required(['auth.view_permission', 'auth.add_permission'])
def permission_list(request):
    permissions = Permission.objects.select_related('content_type').all().order_by('content_type__app_label', 'codename')
    return render(request, 'permission_list.html', {'permissions': permissions})


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
    return render(request, 'permission_form.html', {'form': form})


@jwt_or_session_required
@permission_required('auth.delete_permission')
def permission_delete(request, perm_id):
    perm = get_object_or_404(Permission, id=perm_id)
    if request.method == 'POST':
        perm.delete()
        messages.success(request, 'Permission deleted successfully.')
        return redirect('permission_list')
    return render(request, 'permission_confirm_delete.html', {'permission': perm})
