

# Create your views here.
## login & logout required libraries
from .decorators import allowed_roles
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout

## email related libraries
from django.core.mail import send_mail
from django.conf import settings

## Account activation tokens
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site


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
@csrf_exempt
def ajax_login(request):
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

    user = authenticate(request, username=email, password=password)

    if user is None:
        return JsonResponse(
            {"status": "error", "error": "Incorrect password"},
            status=401
        )

    # ✅ FIX: Set role for superuser if empty
    if user.is_superuser and not user.role:
        user.role = 'ADMIN'
        user.save()
        print(f"Set superuser role to ADMIN for {user.username}")

    login(request, user)
    request.session.save()
    
    print(f"✅ User {user.username} logged in successfully")
    print(f"Role: {user.role}")
    print(f"Is superuser: {user.is_superuser}")

    role = user.role if user.role else 'EMPLOYEE'  # Fallback to EMPLOYEE if no role

    return JsonResponse({
        "status": "success",
        "role": role,
        "username": user.username
    })

# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response


## View Projects
@login_required
def view_projects(request):
    search_query = request.GET.get("search", "")
    
    # Base queryset based on role
    if request.user.role == "ADMIN":
        projects = Projects.objects.all()
    elif request.user.role == "TEAM_LEAD":
        # Team leads see only projects assigned to them
        projects = Projects.objects.filter(assigned_to=request.user)
    else:  # EMPLOYEE
        projects = Projects.objects.filter(assigned_to=request.user)

    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(assigned_to__username__icontains=search_query) |
            Q(status__icontains=search_query)
        ).distinct()

    context = {
        "projects": projects,
        "search_query": search_query
    }
    return render(request, "view_projects.html", context)


## edit Projects
@login_required
@allowed_roles(allowed_roles=["ADMIN","TEAM_LEAD"])
def edit_projects(request, project_id):
    project = get_object_or_404(Projects, id=project_id)
    
    # Check if team lead can edit (only projects they created)
    if request.user.role == "TEAM_LEAD" and project.created_by != request.user:
        messages.error(request, "⛔ You don't have permission to edit this project.")
        return redirect("view_projects")

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
        
        # 🔥 FIX: Add this else clause for invalid forms
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

@login_required
@allowed_roles(allowed_roles=["ADMIN", "TEAM_LEAD"])
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        
        # Get dates for validation
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Validate dates - start must be before end
        if start_date and end_date:
            if start_date > end_date:
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
            messages.success(request, f'✅ Task "{task.name}" updated successfully!')
            return redirect('view_project_detail', project_id=task.project.id)
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
    else:
        form = TaskForm(instance=task)
    
    context = {
        'form': form,
        'task': task,
        'is_edit': True
    }
    return render(request, 'edit_task.html', context)

## delete task
@login_required
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
@login_required
@allowed_roles(allowed_roles=["ADMIN", "TEAM_LEAD", "EMPLOYEE"])
def view_project_detail(request, project_id):
    project = get_object_or_404(Projects, id=project_id)
    
    # Check if team lead has access to this project
    if request.user.role == "TEAM_LEAD" and request.user not in project.assigned_to.all():
        messages.error(request, "You don't have permission to view this project.")
        return redirect('view_projects')
    
    resources = project.resources.all()
    
    # Get tasks under this project
    tasks = Task.objects.filter(project=project).order_by('-created_at')
    
    # Add calculated fields for tasks
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
    
    # Task statistics
    total_tasks = tasks.count()
    ongoing_tasks = tasks.filter(status='ONGOING').count()
    completed_tasks = tasks.filter(status='COMPLETED').count()
    pending_tasks = tasks.filter(status='PENDING').count()

    return render(
        request,
        "view_project_detail.html",
        {
            "project": project,
            "resources": resources,
            "tasks": tasks,
            "total_tasks": total_tasks,
            "ongoing_tasks": ongoing_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
        }
    )
    

## View Users detail
from users.models import UserProfile

@login_required
@allowed_roles(allowed_roles=["ADMIN"])
def view_user_details(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)

    profile, created = UserProfile.objects.get_or_create(
        user=user_obj
    )

    ## Analytics 
    projects_assigned = Projects.objects.filter(
        assigned_to=user_obj
    ).count()

    tasks_assigned = Task.objects.filter(
        assigned_to=user_obj
    ).count()

    completed_tasks = Task.objects.filter(
        assigned_to=user_obj,
        status="COMPLETED"
    ).count()

    # Performance calculation
    performance = 0
    if tasks_assigned > 0:
        performance = int((completed_tasks / tasks_assigned) * 100)


    context = {
        "user_obj": user_obj,
        "profile": profile,
        "projects_assigned": projects_assigned,
        "tasks_assigned": tasks_assigned,
        "completed_tasks": completed_tasks,
        "performance": performance
    }

    return render(request, "view_user_details.html", {
        "user_obj": user_obj,
        "profile": profile
    })


@login_required
def add_project_resource(request, project_id):
    project = get_object_or_404(Projects, id=project_id)

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
@login_required
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
    

from django.views.decorators.csrf import ensure_csrf_cookie
@ensure_csrf_cookie
def login_page(request):
    return render(request, "ajax_login.html")


## Dashboard view
@login_required
def dashboard(request):
    context = {}

    role = request.user.role.upper()  # convert to uppercase to match checks

    if role == "ADMIN":
        context['total_users'] = User.objects.count()
        context['total_projects'] = Projects.objects.count()
        context['total_tasks'] = Task.objects.count()
        context['users'] = User.objects.all()

    elif role == "TEAMLEAD":
    # Flag to indicate Team Lead dashboard
        context['is_teamlead'] = True

    elif role == "EMPLOYEE":
        context['tasks'] = Task.objects.filter(assigned_to=request.user)
        context['projects'] = Projects.objects.filter(assigned_to=request.user)

    return render(request, "dashboard.html", context)



## logout
def logout_view(request):
    logout(request)  # clears session
    return redirect("render_login")


## required logins
from .models import User
@login_required
@allowed_roles(allowed_roles=["ADMIN"])
def admin_dashboard(request):
    # User statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()
    
    # Project statistics
    total_projects = Projects.objects.count()
    ongoing_projects = Projects.objects.filter(status='ONGOING').count()
    
    # Task statistics
    total_tasks = Task.objects.count()
    completed_tasks = Task.objects.filter(status='COMPLETED').count()
    
    # Recent items
    recent_projects = Projects.objects.all().order_by('-start_date')[:5]
    recent_tasks = Task.objects.all().order_by('-created_at')[:5]
    
    # All users for table
    users = User.objects.all()
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'total_projects': total_projects,
        'ongoing_projects': ongoing_projects,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'recent_projects': recent_projects,
        'recent_tasks': recent_tasks,
        'users': users,
    }
    return render(request, 'admin_dashboard.html', context)


# users/views.py
# users/views.py
@login_required
@allowed_roles(allowed_roles=["TEAM_LEAD"])
def teamlead_dashboard(request):
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
    pending_tasks = tasks_from_my_projects.filter(status='PENDING').order_by('-created_at')[:5]
    
    # Team members (all employees - team leads manage all employees)
    team_members = User.objects.filter(role='EMPLOYEE').count()
    active_members = User.objects.filter(role='EMPLOYEE', is_active=True).count()
    
    # Recent projects - only team lead's projects
    recent_projects = my_projects.order_by('-start_date')[:5]
    
    # Get team members list for display
    team_members_list = User.objects.filter(role='EMPLOYEE')[:4]
    
    context = {
        'total_projects': total_projects,
        'active_tasks': active_tasks,
        'completed_tasks': completed_tasks,
        'team_members': team_members,
        'active_members': active_members,
        'recent_projects': recent_projects,
        'pending_tasks': pending_tasks,
        'team_members_list': team_members_list,
        'ongoing_tasks': active_tasks,  # For template compatibility
    }
    return render(request, 'teamlead_dashboard.html', context)



@login_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def employee_dashboard(request):
    print(f"Employee dashboard accessed by: {request.user.username}")
    print(f"Is authenticated: {request.user.is_authenticated}")
    print(f"Session key: {request.session.session_key}")
    user = request.user

    # Tasks assigned to employee
    tasks = Task.objects.filter(assigned_to=user)
    tasks_count = tasks.count()
    ongoing_tasks = tasks.filter(status='ONGOING').count()
    completed_tasks = tasks.filter(status='COMPLETED').count()
    pending_tasks = tasks.filter(status='PENDING').count()
    recent_tasks = tasks.order_by('-created_at')[:5]

    # Projects assigned to employee
    projects = Projects.objects.filter(assigned_to=user)
    projects_count = projects.count()
    ongoing_projects = projects.filter(status='ONGOING').count()
    pending_projects = projects.filter(status='PENDING').count()
    completed_projects = projects.filter(status='COMPLETED').count()

    return render(request, "employee_dashboard.html", {
        "tasks": tasks,
        "tasks_count": tasks_count,
        "ongoing_tasks": ongoing_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "recent_tasks": recent_tasks,
        "projects": projects,
        "projects_count": projects_count,
        "ongoing_projects": ongoing_projects,
        "pending_projects": pending_projects,
        "completed_projects": completed_projects,
    })


@allowed_roles(allowed_roles=["EMPLOYEE"])
def employee_projects(request):
    projects = Projects.objects.filter(assigned_to=request.user)
    return render(request, "employee_projects.html", {"projects": projects})



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

@login_required
@allowed_roles(['ADMIN'])
def edit_user(request, user_id):
    # Get user and their profile
    user = get_object_or_404(User, id=user_id)
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Get all departments and designations for dropdowns
    departments = Department.objects.all()
    designations = Designation.objects.all()

    if request.method == "POST":
        # Get form data
        email = request.POST.get("email")
        username = request.POST.get("username")
        role = request.POST.get("role")
        is_active = request.POST.get("is_active")
        
        # Update user
        user.email = email
        user.username = username
        user.role = role
        user.is_active = (is_active == "True")  # Convert to boolean
        user.save()

        # Update profile
        profile.department_id = request.POST.get("department")
        profile.designation_id = request.POST.get("designation")
        profile.employee_id = request.POST.get("employee_id") or None  # Empty becomes None
        profile.phone = request.POST.get("phone") or None
        profile.date_of_joining = request.POST.get("date_of_joining") or None
        profile.save()

        messages.success(request, "User updated successfully")
        return redirect("admin_view_users")
    
    # For GET request - show the form
    context = {
        "user": user,
        "profile": profile,
        "departments": departments,
        "designations": designations
    }
    return render(request, "edit_user.html", context)



## Members dashboard function
from django.db.models import Q
@login_required
def admin_view_users(request):
    search_query = request.GET.get('search')

    if search_query:
        users = User.objects.filter(
            Q(username__icontains=search_query) |
            Q(role__icontains=search_query)
        )
    else:
        users = User.objects.all()

    context = {
        'users': users
    }

    return render(request, "admin_view_users.html", context)

@login_required
def teamlead_view_users(request):
    # Team leads see all employees (they manage all employees)
    employees = User.objects.filter(role='EMPLOYEE')
    
    # Calculate statistics
    total_employees = employees.count()
    active_count = employees.filter(is_active=True).count()
    
    # Calculate total tasks assigned to all employees
    from Tasks.models import Task
    total_tasks = Task.objects.filter(assigned_to__in=employees).count()
    
    context = {
        'users': employees,
        'total_employees': total_employees,  # This is passed correctly
        'active_count': active_count,
        'total_tasks': total_tasks,
    }
    return render(request, 'teamlead_view_users.html', context)

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

User = get_user_model()

@login_required
@allowed_roles(allowed_roles=["ADMIN"])
def create_user(request):
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

@login_required
@allowed_roles(allowed_roles=["ADMIN"])
def delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)

    # Prevent Admin from deleting themselves
    if user_to_delete == request.user:
        return redirect("admin_dashboard")

    user_to_delete.delete()
    return redirect("admin_dashboard")


# Import Project and Task from their apps
from projects.models import Projects
from Tasks.models import Task
from Tasks.forms import TaskForm 

@login_required
@allowed_roles(allowed_roles=["TEAM_LEAD","ADMIN"])
def assign_task(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        
        # Get dates for validation
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Validate dates - start must be before end
        if start_date and end_date:
            if start_date > end_date:
                context = {
                    'form': form,
                    'date_error': "❌ End date must be after start date"
                }
                return render(request, "assign_task.html", context)
        
        if form.is_valid():
            # Step 1: Save the task instance but don't commit to DB yet
            task = form.save(commit=False)
            
            # Step 2: Get estimated time from the hidden field (if using dropdowns)
            estimated_time = request.POST.get('estimated_time')
            if estimated_time:
                task.estimated_time = int(estimated_time)
            
            # Step 3: Set any additional fields if needed
            assigner = request.user
            
            # Step 4: Save the task to DB
            task.save()
            
            # Step 5: CRITICAL - Save ALL ManyToMany fields (assigned_to AND observers!)
            form.save_m2m()  # This saves BOTH assigned_to and observers relationships
            
            # Step 6: Create notifications for ALL assigned employees
            from notifications.models import Notification
            for employee in task.assigned_to.all():  # Loop through all assigned employees
                if not Notification.objects.filter(
                    user=employee, 
                    message=f'Task "{task.name}" has been assigned to you'
                ).exists():
                    Notification.objects.create(
                        user=employee,
                        message=f'Task "{task.name}" has been assigned to you'
                    )
            
            # Step 7: Create notifications for observers (if any)
            # Create a list of assignee names for the message
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

            messages.success(request, f'Task "{task.name}" assigned successfully to {task.assigned_to.count()} employee(s) with {task.observers.count()} observer(s)! (Est. time: {time_display})')
            # Redirect based on user role
            if request.user.role == "ADMIN":
                return redirect("admin_dashboard")
            else:
                return redirect("teamlead_dashboard")
        else:
            # Form is invalid, show errors
            context = {'form': form}
            return render(request, "assign_task.html", context)
    else:
        form = TaskForm()

    return render(request, "assign_task.html", {"form": form})

## Create Project
from projects.forms import  ProjectResourceFormSet
from users.forms import ProjectForm

@login_required
@allowed_roles(["ADMIN", "TEAM_LEAD"])
def create_project(request):
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
                if resource_form.cleaned_data:
                    resource = resource_form.save(commit=False)
                    resource.project = project
                    resource.save()

            messages.success(request, "✅ Project created successfully!")
            return redirect("view_projects" if request.user.role == "ADMIN" else "teamlead_dashboard")
        
        # 🔥 FIX: Add else clause for invalid forms
        else:
            # Form is invalid - show errors
            if not project_form.is_valid():
                for field, errors in project_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
            
            if not resource_formset.is_valid():
                messages.error(request, "Please check the resources section")
            
            # Stay on the same page with errors
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
@login_required
@allowed_roles(allowed_roles=["EMPLOYEE", "ADMIN", "TEAM_LEAD"])
def task_dashboard(request):
    """Task dashboard showing all tasks in list view"""
    
    # Get tasks based on user role
    if request.user.role == "EMPLOYEE":
        # Employees see only their own tasks
        tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')
    
    elif request.user.role == "TEAM_LEAD":
        # Team Leads see tasks from projects they are assigned to
        my_projects = Projects.objects.filter(assigned_to=request.user)
        my_project_ids = my_projects.values_list('id', flat=True)
        tasks = Task.objects.filter(project_id__in=my_project_ids).order_by('-created_at')
    
    else:  # ADMIN
        # Admins see ALL tasks
        tasks = Task.objects.all().order_by('-created_at')
    
    # Statistics
    total_tasks = tasks.count()
    ongoing_count = tasks.filter(status='ONGOING').count()
    completed_count = tasks.filter(status='COMPLETED').count()
    
    # Calculate overdue count and send notifications
    now = timezone.now()
    overdue_count = 0
    from notifications.models import Notification
    
    for task in tasks:
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
                
                # 1. Notify task owner (assigned_by)
                if task.assigned_by:
                    # Check if already notified recently (optional)
                    existing = Notification.objects.filter(
                        user=task.assigned_by,
                        message__icontains=f"Task '{task.name}' is overdue",
                        created_at__date=now.date()
                    ).exists()
                    
                    if not existing:
                        Notification.objects.create(
                            user=task.assigned_by,
                            message=f"⚠️ Task '{task.name}' (Project: {task.project.name}) is overdue!",
                            is_read=False
                        )
                
                # 2. Notify all assignees
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
                
                # 3. Notify all observers
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
    
    print(f"Total overdue count: {overdue_count}")
    
    context = {
        'tasks': tasks,
        'total_tasks': total_tasks,
        'ongoing_count': ongoing_count,
        'completed_count': completed_count,
        'overdue_count': overdue_count,
        'now': now,
    }
    return render(request, 'task_dashboard.html', context)



## TaskSummary 
from django.http import JsonResponse

@login_required
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
@login_required
@allowed_roles(allowed_roles=["EMPLOYEE", "TEAM_LEAD", "ADMIN"])
def employee_tasks(request):
    task_id = request.GET.get('task_id')
    employee_id = request.GET.get('employee_id')
    
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
@allowed_roles(['ADMIN'])
def departments(request):
    departments = Department.objects.all()

    # Handle creation of a new department
    if request.method == "POST":
        new_dept_name = request.POST.get("department_name")
        if new_dept_name:
            Department.objects.create(name=new_dept_name)
            messages.success(request, f"Department '{new_dept_name}' created successfully!")
            return redirect("departments")

    return render(request, "department_list.html", {"departments": departments})

## Create departments
@login_required
@allowed_roles(['ADMIN'])
def create_department(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            Department.objects.create(name=name)
            messages.success(request, "Department created successfully!")
            return redirect("departments")
    return render(request, "create_department.html", {"action": "Create"})


# Show all users in a department
def department_detail(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    # Follow the OneToOne relation from User to UserProfile
    users_in_dept = User.objects.filter(profile__department=department)
    return render(request, "department_detail.html", {
        "department": department,
        "users": users_in_dept
    })

## delete_department
@login_required
@allowed_roles(['ADMIN'])
def delete_department(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    if request.method == "POST":
        department.delete()
        messages.success(request, "Department deleted successfully!")
        return redirect("departments")  # your department list view name
    return redirect("departments")

# <!--Designation-->
# List all designations
@allowed_roles(['ADMIN'])
def designations(request):
    designations = Designation.objects.all()
    return render(request, "designation_list.html", {"designations": designations})


@login_required
@allowed_roles(['ADMIN'])
def create_designation(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            Designation.objects.create(name=name)
            messages.success(request, "Designation created successfully!")
            return redirect("designations")
    return render(request, "designation_form.html", {"action": "Create"})



# Show all users in a designation
def designation_detail(request, desig_id):
    designation = get_object_or_404(Designation, id=desig_id)
    users_in_desig = User.objects.filter(profile__designation=designation)
    return render(request, "designation_detail.html", {
        "designation": designation,
        "users": users_in_desig
    })

## delete designation
@login_required
@allowed_roles(['ADMIN'])
def delete_designation(request, desig_id):
    desig = get_object_or_404(Designation, id=desig_id)
    desig.delete()
    messages.success(request, "Designation deleted successfully!")
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
@login_required 
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


## home page
def home(request):
    return render(request, "home.html")

