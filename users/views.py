

# Create your views here.
## login & logout required libraries
from .decorators import allowed_roles
from django.contrib.auth.decorators import login_required
from users.decorators import jwt_or_session_required
from django.contrib.auth import authenticate, login, logout

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

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages

## for notification logic
from notifications.models import Notification
from users.models import User

## Used for Session based login
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        print(email)
        password = request.POST.get("password")
        
        #email = request.POST.get("email")

        user = authenticate(request, email=email, password=password)
        print("USER:", user)
        if user is not None:
            if user.is_active:
                login(request, user)



            # Role-based redirect
            if user.role == "ADMIN":
                return redirect("admin_dashboard")
            elif user.role == "TEAM_LEAD":
                return redirect("teamlead_dashboard")
            elif user.role == "EMPLOYEE":
                return redirect("employee_dashboard")
    else:
            messages.error(request, "Invalid username or password")

    return render(request, "login.html")


from django.http import JsonResponse
import json

from rest_framework_simplejwt.tokens import RefreshToken
from django.http import JsonResponse
from django.contrib.auth import authenticate,get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt
import json
User = get_user_model()

## ajax login
from rest_framework_simplejwt.tokens import RefreshToken  # Add this import at the top
@csrf_exempt
def ajax_login(request):
    """
    LOGIN VIEW - Returns BOTH session cookie AND JWT token
    
    WHY BOTH?
    - Session Cookie: Used by web browsers (existing functionality)
    - JWT Token: Used by Postman/mobile apps (no CSRF issues)
    
    This allows ONE login endpoint to serve ALL clients!
    """
    
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "error": "Invalid request method"},
            status=405
        )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "error": "Invalid JSON"},
            status=400
        )

    email = data.get("email")
    password = data.get("password")

    if not email:
        return JsonResponse(
            {"status": "error", "error": "Email is required"},
            status=400
        )

    if not password:
        return JsonResponse(
            {"status": "error", "error": "Password is required"},
            status=400
        )
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse(
            {"status": "error", "error": "Email does not exist"},
            status=401
        )
    
    if not user.is_active:
        return JsonResponse(
            {"status": "error", "error": "Your account is inactive. Please contact the administrator."},
            status=403
        )

    # Authenticate user
    user = authenticate(request, username=email, password=password)

    if user is None:
        return JsonResponse(
            {"status": "error", "error": "Incorrect password"},
            status=401
        )

    # Set role for superuser if empty
    if user.is_superuser and not user.role:
        user.role = 'ADMIN'
        user.save()
        print(f"Set superuser role to ADMIN for {user.username}")

    # ========== PART 1: SESSION AUTHENTICATION (For Web Browsers) ==========
    # This creates a session cookie that browsers automatically store and send
    login(request, user)
    request.session.save()
    
    print(f"✅ User {user.username} logged in successfully")
    print(f"Role: {user.role}")
    print(f"Is superuser: {user.is_superuser}")
    
    role = user.role if user.role else 'EMPLOYEE'

    # ========== PART 2: JWT TOKEN GENERATION (For Postman/API) ==========
    # Generate JWT tokens that Postman can use in Authorization header
    # RefreshToken.for_user(user) creates a new token containing user info
    refresh = RefreshToken.for_user(user)
    
    # Get the actual token strings
    access_token = str(refresh.access_token)  # Short-lived token (60 min)
    refresh_token = str(refresh)               # Long-lived token (1 day)
    
    # WHAT'S IN THE TOKEN?
    # The token contains:
    # - user_id: user.id
    # - exp: expiration timestamp
    # - iat: issued at timestamp
    # - token_type: 'access' or 'refresh'
    # This is automatically handled by simplejwt

    # ========== PART 3: RESPONSE (Contains BOTH) ==========
    # Return both session data (for web) AND JWT tokens (for Postman)
    return JsonResponse({
        "status": "success",
        "role": role,
        "username": user.username,
        
        # 🔑 JWT TOKENS - This is what Postman will use
        "access_token": access_token,
        "refresh_token": refresh_token,
        
        # 👤 USER DETAILS - Helpful for frontend
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
    })

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


## View Projects
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
@jwt_or_session_required
def view_projects(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get("search", "").strip()
        page = request.GET.get("page", 1)
        page_size = request.GET.get("page_size", 10)
        
        # Base queryset based on role
        if request.user.role == "ADMIN":
            projects = Projects.objects.all()
        elif request.user.role == "TEAM_LEAD":
            projects = Projects.objects.filter(assigned_to=request.user)
        else:  # EMPLOYEE
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
                'view_url': f"/view_project_detail/{project.id}/",
                'delete_url': f"/delete_project/{project.id}/"
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
    
    # Base queryset based on role
    if request.user.role == "ADMIN":
        projects = Projects.objects.all()
    elif request.user.role == "TEAM_LEAD":
        projects = Projects.objects.filter(assigned_to=request.user)
    else:  # EMPLOYEE
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
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import ValidationError

@jwt_or_session_required
@allowed_roles(allowed_roles=["ADMIN","TEAM_LEAD"])
def edit_projects(request, project_id):
    project = get_object_or_404(Projects, id=project_id)
    
    # Check if team lead can edit (only projects they created)
    if request.user.role == "TEAM_LEAD" and project.created_by != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': "You don't have permission to edit this project."
            }, status=403)
        messages.error(request, "⛔ You don't have permission to edit this project.")
        return redirect("view_projects")

    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "POST":
            form = ProjectForm(request.POST, instance=project)
            
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
            form = ProjectForm(instance=project)
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
        form = ProjectForm(request.POST, instance=project)
        
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
        form = ProjectForm(instance=project)

    return render(request, "edit_projects.html", {
        "form": form,
        "project": project
    })

@jwt_or_session_required
@allowed_roles(allowed_roles=["ADMIN", "TEAM_LEAD"])
def edit_task(request, task_id):
    """Edit Task - AJAX enabled"""
    
    task = get_object_or_404(Task, id=task_id)
    task = Task.objects.prefetch_related('assigned_by', 'assigned_to', 'observers').get(id=task_id)
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        
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
        form = TaskForm(instance=task)
    
    context = {
        'form': form,
        'task': task,
        'is_edit': True
    }
    return render(request, 'edit_task.html', context)


## delete task
@jwt_or_session_required
@allowed_roles(allowed_roles=["ADMIN", "TEAM_LEAD"])
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
@allowed_roles(allowed_roles=["ADMIN", "TEAM_LEAD", "EMPLOYEE"])
def view_project_detail(request, project_id):
    project = get_object_or_404(Projects, id=project_id)
    
    # Check if team lead has access
    if request.user.role == "TEAM_LEAD" and request.user not in project.assigned_to.all():
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
from users.models import UserProfile
@jwt_or_session_required
@allowed_roles(allowed_roles=["ADMIN"])
def view_user_details(request, user_id):
    # Only allow GET requests for this view
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
                "date_joined": user_obj.date_joined.strftime('%Y-%m-%d') if user_obj.date_joined else None
            },
            "profile": {
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
@allowed_roles(allowed_roles=["TEAM_LEAD", "ADMIN"])
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
            if request.user.role == "ADMIN":
                return redirect("view_projects")
            else:
                return redirect("teamlead_dashboard")
    
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
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        role = request.user.role.upper()
        
        if role == "ADMIN":
            total_users = User.objects.count()
            total_projects = Projects.objects.count()
            total_tasks = Task.objects.count()
            users = User.objects.all()
            
            users_data = []
            for user in users:
                users_data.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'is_active': user.is_active,
                })
            
            return JsonResponse({
                'success': True,
                'role': 'ADMIN',
                'stats': {
                    'total_users': total_users,
                    'total_projects': total_projects,
                    'total_tasks': total_tasks,
                },
                'users': users_data
            })
        
        elif role == "TEAMLEAD":
            my_projects = Projects.objects.filter(assigned_to=request.user)
            my_project_ids = my_projects.values_list('id', flat=True)
            tasks_from_my_projects = Task.objects.filter(project_id__in=my_project_ids)
            
            return JsonResponse({
                'success': True,
                'role': 'TEAMLEAD',
                'stats': {
                    'total_projects': my_projects.count(),
                    'active_tasks': tasks_from_my_projects.filter(status='ONGOING').count(),
                    'completed_tasks': tasks_from_my_projects.filter(status='COMPLETED').count(),
                    'team_members': User.objects.filter(role='EMPLOYEE').count(),
                }
            })
        
        elif role == "EMPLOYEE":
            tasks = Task.objects.filter(assigned_to=request.user)
            projects = Projects.objects.filter(assigned_to=request.user)
            
            return JsonResponse({
                'success': True,
                'role': 'EMPLOYEE',
                'stats': {
                    'tasks_count': tasks.count(),
                    'ongoing_tasks': tasks.filter(status='ONGOING').count(),
                    'completed_tasks': tasks.filter(status='COMPLETED').count(),
                    'pending_tasks': tasks.filter(status='PENDING').count(),
                    'projects_count': projects.count(),
                }
            })
        
        return JsonResponse({'success': False, 'error': 'Invalid role'}, status=400)
    
    # Regular request - return template
    return render(request, "dashboard.html")



## logout
@jwt_or_session_required
def logout_view(request):
    logout(request)  # clears session
    return redirect("render_login")


## required logins
from .models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

## Admin dashboard 
@jwt_or_session_required
@allowed_roles(allowed_roles=["ADMIN"])
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
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'edit_url': f"/edit-user/{user.id}/",
                'delete_url': f"/delete_user/{user.id}/"
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
@allowed_roles(allowed_roles=["TEAM_LEAD"])
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
        
        # Team members (all employees - team leads manage all employees)
        team_members_total = User.objects.filter(role='EMPLOYEE').count()
        active_members = User.objects.filter(role='EMPLOYEE', is_active=True).count()
        
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
        all_team_members = User.objects.filter(role='EMPLOYEE').order_by('username')
        paginator = Paginator(all_team_members, members_page_size)
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
@allowed_roles(allowed_roles=["EMPLOYEE"])
def employee_dashboard(request):
    print(f"Employee dashboard accessed by: {request.user.username}")
    print(f"Is authenticated: {request.user.is_authenticated}")
    print(f"Session key: {request.session.session_key}")
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
@allowed_roles(allowed_roles=["EMPLOYEE"])
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
                'view_url': f"/view_project_detail/{project.id}/"
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
from .forms import UserRegisterForm
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
@jwt_or_session_required
@allowed_roles(['ADMIN'])
def edit_user(request, user_id):
    """Edit User - AJAX enabled"""
    
    # Get user and their profile
    user = get_object_or_404(User, id=user_id)
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Get all departments and designations for dropdowns
    departments = Department.objects.all()
    designations = Designation.objects.all()
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == "POST":
        # Get form data
        email = request.POST.get("email")
        username = request.POST.get("username")
        role = request.POST.get("role")
        is_active = request.POST.get("is_active")
        
        # Validate required fields
        errors = {}
        if not email:
            errors['email'] = ['Email is required']
        if not username:
            errors['username'] = ['Username is required']
        if not role:
            errors['role'] = ['Role is required']
        
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
                    "designations": designations
                }
                return render(request, "edit_user.html", context)
        
        # Update user
        user.email = email
        user.username = username
        user.role = role
        user.is_active = (is_active == "True")
        user.save()

        # Update profile
        profile.department_id = request.POST.get("department")
        profile.designation_id = request.POST.get("designation")
        profile.employee_id = request.POST.get("employee_id") or None
        profile.phone = request.POST.get("phone") or None
        profile.date_of_joining = request.POST.get("date_of_joining") or None
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
        "designations": designations
    }
    return render(request, "edit_user.html", context)


## Members dashboard function
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

## Admin view users
@csrf_exempt
@jwt_or_session_required
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
            # Role badge class
            role_class = ''
            if user.role == 'ADMIN':
                role_class = 'bg-purple-100 text-purple-700'
            elif user.role == 'TEAM_LEAD':
                role_class = 'bg-blue-100 text-blue-700'
            else:
                role_class = 'bg-gray-100 text-gray-700'
            
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'role_display': user.role,
                'role_class': role_class,
                'is_active': user.is_active,
                'view_url': f"/view_user_details/{user.id}/",
                'delete_url': f"/delete_user/{user.id}/"
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
def teamlead_view_users(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get('search', '').strip()
        page = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 10)
        
        # Team leads see all employees (they manage all employees)
        employees = User.objects.filter(role='EMPLOYEE')
        
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
        total_employees = User.objects.filter(role='EMPLOYEE').count()
        active_count = User.objects.filter(role='EMPLOYEE', is_active=True).count()
        total_tasks = Task.objects.filter(assigned_to__in=User.objects.filter(role='EMPLOYEE')).count()
        
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
                'tasks_url': f"/employee_tasks/?employee_id={user.id}",
                'assign_task_url': f"/assign_task/?employee={user.id}"
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
def activate_user(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Your account has been activated. You can now log in.")
        return redirect("login")
    else:
        messages.error(request, "Activation link is invalid!")
        return redirect("register")
    


## Create new user with role and save to database
from django.contrib.auth import get_user_model
# User = get_user_model()
@csrf_exempt
@jwt_or_session_required
@allowed_roles(["ADMIN"])
def create_user(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "POST":
            user_form = UserRegisterForm(request.POST)
            profile_form = UserProfileForm(request.POST)

            errors = {}
            
            # Validate forms
            if not user_form.is_valid():
                for field, error_list in user_form.errors.items():
                    errors[f'user_{field}'] = error_list
            
            if not profile_form.is_valid():
                for field, error_list in profile_form.errors.items():
                    errors[f'profile_{field}'] = error_list
            
            # If there are validation errors
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)
            
            # Forms are valid, proceed with user creation
            try:
                # Step 1: Save the User (but don't commit to DB yet)
                user = user_form.save(commit=False)
                user.set_password(user_form.cleaned_data['password1'])
                user.save()  # ✅ Now user is saved to database
                
                # Step 2: The SIGNAL automatically creates a UserProfile here!
                # When user.save() runs, the signal fires and creates a profile
                
                # Step 3: Get the existing profile created by the signal
                profile = user.profile  # ← This gets the profile from the database
                
                # Step 4: Update the existing profile with form data
                profile.employee_id = profile_form.cleaned_data.get('employee_id')
                profile.phone = profile_form.cleaned_data.get('phone')
                profile.department = profile_form.cleaned_data.get('department')
                profile.designation = profile_form.cleaned_data.get('designation')
                profile.date_of_joining = profile_form.cleaned_data.get('date_of_joining')
                profile.save()  # ✅ Update the profile with new data

                # Convert department and designation to strings for JSON
                department_name = profile.department.name if profile.department else None
                designation_name = profile.designation.name if profile.designation else None

                # Return success response with user data
                return JsonResponse({
                    'success': True,
                    'message': f"User '{user.username}' created successfully!",
                    'redirect_url': request.POST.get('redirect_url', '/admin-dashboard/'),
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                        'role': user.role,
                        'employee_id': profile.employee_id,
                        'department': department_name,  # ✅ Fixed - now string
                        'designation': designation_name  # ✅ Fixed - now string
                    }
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'errors': {
                        'system_error': [f"Error creating user: {str(e)}"]
                    }
                }, status=500)
        
        # GET request - return form structure if needed
        elif request.method == "GET":
            user_form = UserRegisterForm()
            profile_form = UserProfileForm()
            
            # Get field definitions for dynamic form rendering
            user_fields = {}
            for field_name, field in user_form.fields.items():
                user_fields[field_name] = {
                    'label': str(field.label),
                    'required': field.required,
                    'help_text': field.help_text,
                    'type': field.widget.__class__.__name__
                }
            
            profile_fields = {}
            for field_name, field in profile_form.fields.items():
                profile_fields[field_name] = {
                    'label': str(field.label),
                    'required': field.required,
                    'help_text': field.help_text,
                    'type': field.widget.__class__.__name__
                }
            
            return JsonResponse({
                'success': True,
                'user_fields': user_fields,
                'profile_fields': profile_fields
            })
    
    # Handle regular (non-AJAX) request
    if request.method == "POST":
        user_form = UserRegisterForm(request.POST)
        profile_form = UserProfileForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            try:
                # Step 1: Save the User (but don't commit to DB yet)
                user = user_form.save(commit=False)
                user.set_password(user_form.cleaned_data['password1'])
                user.save()  # ✅ Now user is saved to database
                
                # Step 2: The SIGNAL automatically creates a UserProfile here!
                # When user.save() runs, the signal fires and creates a profile
                
                # Step 3: Get the existing profile created by the signal
                profile = user.profile  # ← This gets the profile from the database
                
                # Step 4: Update the existing profile with form data
                profile.employee_id = profile_form.cleaned_data.get('employee_id')
                profile.phone = profile_form.cleaned_data.get('phone')
                profile.department = profile_form.cleaned_data.get('department')
                profile.designation = profile_form.cleaned_data.get('designation')
                profile.date_of_joining = profile_form.cleaned_data.get('date_of_joining')
                profile.save()  # ✅ Update the profile with new data

                messages.success(request, f"User '{user.username}' created successfully!")
                return redirect("admin_dashboard")
                
            except Exception as e:
                print(f"ERROR: {str(e)}")
                messages.error(request, f"Error creating user: {str(e)}")
        else:
            # Form validation failed
            if not user_form.is_valid():
                for field, errors in user_form.errors.items():
                    for error in errors:
                        messages.error(request, f"User Form - {field}: {error}")
            
            if not profile_form.is_valid():
                for field, errors in profile_form.errors.items():
                    for error in errors:
                        messages.error(request, f"Profile Form - {field}: {error}")
    else:
        user_form = UserRegisterForm()
        profile_form = UserProfileForm()

    return render(request, "create_user.html", {
        "user_form": user_form,
        "profile_form": profile_form
    })


## delete user
from django.shortcuts import get_object_or_404
@jwt_or_session_required
@allowed_roles(allowed_roles=["ADMIN"])
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
from Tasks.models import Task
from Tasks.forms import TaskForm 
## Assign Task
@jwt_or_session_required
@allowed_roles(allowed_roles=["TEAM_LEAD","ADMIN"])
def assign_task(request):
    """Assign Task - AJAX enabled"""
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == "POST":
        form = TaskForm(request.POST)
        
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
                    'time_display': time_display
                })
            else:
                # Regular form submission fallback
                messages.success(request, f'Task "{task.name}" assigned successfully to {task.assigned_to.count()} employee(s)!')
                if request.user.role == "ADMIN":
                    return redirect("admin_dashboard")
                else:
                    return redirect("teamlead_dashboard")
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
        form = TaskForm()

    return render(request, "assign_task.html", {"form": form})

## Create Project
from projects.forms import  ProjectResourceFormSet
from users.forms import ProjectForm
## Create Project
@jwt_or_session_required
@allowed_roles(["ADMIN", "TEAM_LEAD"])
def create_project(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == "POST":
            project_form = ProjectForm(request.POST)
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
                
                if project_form.cleaned_data.get('assigned_to'):
                    project.assigned_to.set(project_form.cleaned_data['assigned_to'])
                # Save resources
                resource_count = 0
                for resource_form in resource_formset:
                    if resource_form.cleaned_data and not resource_form.cleaned_data.get('DELETE', False):
                        resource = resource_form.save(commit=False)
                        resource.project = project
                        resource.save()
                        resource_count += 1
                
                # Determine redirect URL based on user role
                redirect_url = request.POST.get('redirect_url', '')
                if not redirect_url:
                    redirect_url = "view_projects" if request.user.role == "ADMIN" else "teamlead_dashboard"
                
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
            project_form = ProjectForm()
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
        project_form = ProjectForm(request.POST)
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
            
            for resource_form in resource_formset:
                if resource_form.cleaned_data and not resource_form.cleaned_data.get('DELETE', False):
                    resource = resource_form.save(commit=False)
                    resource.project = project
                    resource.save()

            messages.success(request, "✅ Project created successfully!")
            return redirect("view_projects" if request.user.role == "ADMIN" else "teamlead_dashboard")
        
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
        project_form = ProjectForm()
        resource_formset = ProjectResourceFormSet()

    context = {
        "form": project_form,
        "resource_formset": resource_formset
    }
    return render(request, "create_project.html", context)


## task_dashboard
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
@jwt_or_session_required
@allowed_roles(allowed_roles=["EMPLOYEE", "ADMIN", "TEAM_LEAD"])
def task_dashboard(request):
    """Task dashboard showing all tasks in list view"""
    
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get pagination parameters
        page = request.GET.get("page", 1)
        page_size = request.GET.get("page_size", 10)
        
        # Get tasks based on user role
        if request.user.role == "EMPLOYEE":
            tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')
        elif request.user.role == "TEAM_LEAD":
            my_projects = Projects.objects.filter(assigned_to=request.user)
            my_project_ids = my_projects.values_list('id', flat=True)
            tasks = Task.objects.filter(project_id__in=my_project_ids).order_by('-created_at')
        else:  # ADMIN
            tasks = Task.objects.all().order_by('-created_at')
        
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
                'view_url': f"/employee_tasks/?task_id={task.id}"
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
    if request.user.role == "EMPLOYEE":
        tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')
    elif request.user.role == "TEAM_LEAD":
        my_projects = Projects.objects.filter(assigned_to=request.user)
        my_project_ids = my_projects.values_list('id', flat=True)
        tasks = Task.objects.filter(project_id__in=my_project_ids).order_by('-created_at')
    else:  # ADMIN
        tasks = Task.objects.all().order_by('-created_at')

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
@allowed_roles(allowed_roles=["EMPLOYEE", "ADMIN"])
def add_task_summary(request, task_id):
    """Add summary to a task - AJAX enabled"""
    
    try:
        # Allow admins to access any task
        if request.user.role == "ADMIN":
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
@jwt_or_session_required
@allowed_roles(allowed_roles=["EMPLOYEE", "TEAM_LEAD", "ADMIN"])
def employee_tasks(request):
    task_id = request.GET.get('task_id')
    employee_id = request.GET.get('employee_id')
    
    # Handle AJAX request - return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Case 1: Team lead viewing specific employee's tasks
        if employee_id and request.user.role in ['TEAM_LEAD', 'ADMIN']:
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
        
        # Case 2: Viewing single task by ID
        elif task_id:
            task = get_object_or_404(Task, id=task_id)
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
    # Case 1: Team lead viewing specific employee's tasks
    if employee_id and request.user.role in ['TEAM_LEAD', 'ADMIN']:
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
        
        # FIXED: Permission check for employees with ManyToManyField
        if request.user.role == "EMPLOYEE":
            # Check if current user is in the assigned_to list
            if not task.assigned_to.filter(id=request.user.id).exists():
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
@jwt_or_session_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def update_task_status(request, task_id):

    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    if request.method == "POST":
        new_status = request.POST.get("status")

        # Workflow control
        if task.status == "PENDING" and new_status == "ONGOING":
            task.status = "ONGOING"
            task.save()

        elif task.status == "ONGOING" and new_status == "COMPLETED":
            task.status = "COMPLETED"
            task.save()

        return redirect("employee_tasks")

    return render(request, "update_task_status.html", {
        "task": task,
        "status_choices": Task.STATUS_CHOICES
    })


## start task
from django.utils import timezone
from django.urls import reverse
import datetime
## START TASK - AJAX VERSION
@jwt_or_session_required
@allowed_roles(allowed_roles=["EMPLOYEE", "ADMIN"])
def start_task(request, task_id):
    """Start a task - AJAX enabled"""
    
    # Allow admins to access any task, employees only their own
    if request.user.role == "ADMIN":
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
    
    return JsonResponse({
        'success': True,
        'message': f'Task "{task.name}" started successfully!',
        'task_id': task.id,
        'status': 'ONGOING',
        'start_time': task.start_time.isoformat()
    })


## PAUSE TASK - AJAX VERSION
@jwt_or_session_required
@allowed_roles(allowed_roles=["EMPLOYEE", "ADMIN"])
def pause_task(request, task_id):
    """Pause an ongoing task - AJAX enabled"""
    
    # Allow admins to access any task, employees only their own
    if request.user.role == "ADMIN":
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

    return JsonResponse({
        'success': True,
        'message': f'Task "{task.name}" paused.',
        'task_id': task.id,
        'paused_time': task.paused_time.isoformat()
    })


## RESUME TASK - AJAX VERSION
@jwt_or_session_required
@allowed_roles(allowed_roles=["EMPLOYEE", "ADMIN"])
def resume_task(request, task_id):
    """Resume a paused task - AJAX enabled"""
    
    # Allow admins to access any task, employees only their own
    if request.user.role == "ADMIN":
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

    return JsonResponse({
        'success': True,
        'message': f'Task "{task.name}" resumed.',
        'task_id': task.id
    })


## COMPLETE TASK - AJAX VERSION
@jwt_or_session_required
@allowed_roles(allowed_roles=["EMPLOYEE", "ADMIN"])
def complete_task(request, task_id):
    """Complete a task - AJAX enabled with JSON response"""
    
    # Allow admins to access any task, employees only their own
    if request.user.role == "ADMIN":
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

    # Notify all Admins and Team Leads
    observers = User.objects.filter(role__in=["ADMIN", "TEAM_LEAD"])
    employee_name = request.user.get_full_name() or request.user.username
    message = f"Task '{task.name}' has been completed by {employee_name}. Time spent: {time_display}"
    
    for user in observers:
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
@allowed_roles(allowed_roles=["ADMIN"])
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
@allowed_roles(['ADMIN'])
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
@allowed_roles(['ADMIN'])
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
@allowed_roles(['ADMIN'])
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
@allowed_roles(allowed_roles=["ADMIN"])
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
@allowed_roles(['ADMIN'])
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
                "role": user.role,
                "role_display": user.get_role_display(),
                "department": user.profile.department.name if user.profile.department else "N/A",
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
@allowed_roles(['ADMIN'])
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


# Only logged-in users can access
# Allow POST requests from our forms
# users/views.py
from services.gemini_service import GeminiService
@jwt_or_session_required
@csrf_exempt    
def ai_generate_description(request):
    """
    API endpoint for AI-powered task descriptions.
    
    Why this structure?
    - POST only (we're creating something)
    - Returns JSON (for JavaScript to use)
    - Has clear success/error format
    """
    
    # Step 1: Check if it's a POST request
    if request.method != "POST":
        return JsonResponse({
            'success': False,
            'error': 'This endpoint only accepts POST requests'
        }, status=405)  # 405 = Method Not Allowed
    
    # Step 2: Try to parse the JSON data
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON format'
        }, status=400)  # 400 = Bad Request
    
    # Step 3: Extract data from request
    task_name = data.get('task_name', '').strip()
    project_name = data.get('project_name', '')
    current_description = data.get('current_description', '')
    action = data.get('action', 'generate')
    
    # Step 4: Validate required fields
    if not task_name:
        return JsonResponse({
            'success': False,
            'error': 'Task name is required'
        }, status=400)
    
    # Step 5: Initialize AI service
    ai_service = GeminiService()
    
    # Step 6: Perform the requested action
    if action == 'enhance' and current_description:
        result = ai_service.enhance_description(current_description, task_name)
    else:
        result = ai_service.gen_task_description(task_name, project_name)
    
    # Step 7: Return the result
    return JsonResponse(result)

## User Analytics
@jwt_or_session_required
@allowed_roles(['ADMIN'])
def user_analytics(request):
    users = User.objects.all().order_by('username')
    selected_user_id = request.GET.get('user_id')
    selected_user = None
    
    # Check if requesting top performers
    get_top_performers = request.GET.get('get_top_performers') == 'true'
    
    if get_top_performers:
        # Calculate top performers for all active users
        all_users = User.objects.filter(is_active=True)
        top_performers = []
        
        for user in all_users:
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
                    'role_display': user.get_role_display(),
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
        tasks = Task.objects.filter(assigned_to=selected_user)
        projects = Projects.objects.filter(assigned_to=selected_user)
    else:
        tasks = Task.objects.all()
        projects = Projects.objects.all()

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

    # Return JSON if AJAX (for user selection)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'analytics': analytics,
            'selected_user': selected_user.username if selected_user else 'All Users'
        })

    # Normal page render
    return render(request, 'user_analytics.html', {
        'users': users,
        'selected_user': selected_user,
        'analytics': analytics
    })

## home page
def home(request):
    return render(request, "home.html")

