

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
## ajax_login
from rest_framework_simplejwt.tokens import RefreshToken

# def ajax_login(request):
#     if request.method != "POST":
#         return JsonResponse({
#             "status": "error",
#             "message": "Invalid request method"
#         }, status=405)

#     try:
#         data = json.loads(request.body)
#     except json.JSONDecodeError:
#         return JsonResponse({
#             "status": "error",
#             "message": "Invalid JSON"
#         }, status=400)

#     username = data.get("username")
#     password = data.get("password")

#     if not username or not password:
#         return JsonResponse({
#             "status": "error",
#             "message": "Username and password required"
#         }, status=400)

#     user = authenticate(request, username=username, password=password)
#     if user is None:
#         return JsonResponse({
#             "status": "error",
#             "message": "Invalid credentials"
#         }, status=401)

#     login(request, user)

#     refresh = RefreshToken.for_user(user)

#     return JsonResponse({
#         "status": "success",
#         "access": str(refresh.access_token),
#         "refresh": str(refresh)
#     })
from django.http import JsonResponse
from django.contrib.auth import authenticate,get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt
import json
User = get_user_model()

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
        User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse(
            {"status": "error", "error": "Email does not exist"},
            status=401
        )

    user = authenticate(request, username=email, password=password)

    if user is None:
        return JsonResponse(
            {"status": "error", "error": "Incorrect password"},
            status=401
        )

    login(request, user)

    # Example role logic — adjust to your model
    role = getattr(user, "role", "EMPLOYEE")     ## getattr(object, "attribute_name", default_value) -- getattr() is a Python function used to safely get an attribute from an object.

    return JsonResponse({
        "status": "success",
        "role": role
    })

    # from django.contrib.auth import get_user_model
    # User = get_user_model()

    # Find user by email or username
    # try:
    #     if email:
    #         user_obj = User.objects.get(email=email)
    # except User.DoesNotExist:
    #     return JsonResponse(
    #         {"status": "error", "message": "User does not exist"},
    #         status=401
    #     )

    # # Authenticate using username (Django requires username internally)
    # user = authenticate(request,username=user_obj, password=password)
    # print("gghghghg")
    # if user is None:
    #     return JsonResponse(
    #         {"status": "error", "message": "Incorrect password"},
    #         status=401
    #     )


    # refresh = RefreshToken.for_user(user)

    # return JsonResponse({
    #     "status": "success",
    #     "role" : user.role,
    #     "access": str(refresh.access_token),
    #     "refresh": str(refresh),
        
    # })

# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response

# @api_view(["GET", "POST"])
# @permission_classes([IsAuthenticated])
# def protected_view(request):
#     return Response({
#         "status": "success",
#         "user": request.user.username
#     })

## View Projects
def view_projects(request):

    search_query = request.GET.get("search", "")

    projects = Projects.objects.all()

    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(assigned_to__username__icontains=search_query) |
            Q(status__icontains=search_query)
        )

    context = {
        "projects": projects,
        "search_query": search_query
    }

    return render(request, "view_projects.html", context)

## edit Projects
@login_required
@allowed_roles(allowed_roles=["ADMIN","TEAM_LEAD"])
def edit_projects(request,project_id):
    project = get_object_or_404(Projects,id = project_id)

    if request.method == "POST":
        form = ProjectForm(request.POST,instance=project)
        if form.is_valid():
            form.save()
            return redirect("view_projects")
        
    else:
        form = ProjectForm(instance=project)

    return render(request,"edit_projects.html" , {
        "form": form,
        "project":project
    })


## edit project
@login_required
@allowed_roles(allowed_roles=["ADMIN", "TEAM_LEAD"])
def edit_task(request, task_id):
    """Edit an existing task"""
    task = get_object_or_404(Task, id=task_id)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            # Save the task
            updated_task = form.save(commit=False)
            updated_task.save()
            
            # Save ManyToMany fields (observers)
            form.save_m2m()
            
            messages.success(request, f'Task "{task.name}" updated successfully!')
            
            # Redirect back to project details
            return redirect('view_project_detail', project_id=task.project.id)
        else:
            # Form is invalid, show errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
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
    """Delete a task"""
    task = get_object_or_404(Task, id=task_id)
    project_id = task.project.id
    task_name = task.name
    
    if request.method == 'POST':
        task.delete()
        messages.success(request, f'Task "{task_name}" deleted successfully!')
        return redirect('view_project_detail', project_id=project_id)
    
    # GET request - show confirmation page
    context = {
        'task': task
    }
    return render(request, 'delete_task_confirm.html', context)





# ## view_project_details
@login_required
@allowed_roles(allowed_roles=["ADMIN", "TEAM_LEAD", "EMPLOYEE"])
def view_project_detail(request, project_id):
    project = get_object_or_404(Projects, id=project_id)
    resources = project.resources.all()
    
    # Get all tasks under this project
    tasks = Task.objects.filter(project=project).order_by('-created_at')
    
    # Add calculated fields for tasks (for time display)
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
            # Format completed task time WITHOUT milliseconds
            total_seconds = int(task.total_time.total_seconds())  # Convert to int to remove milliseconds
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
    project = get_object_or_404(Projects, id=id)
    project.delete()

    # role-based redirect
    if request.user.role == "ADMIN":
        return redirect("view_projects")
    else:
        return redirect("teamlead_dashboard")
    

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

@login_required
# users/views.py
# users/views.py
@login_required
@allowed_roles(allowed_roles=["TEAM_LEAD"])
def teamlead_dashboard(request):
    # Get statistics
    total_projects = Projects.objects.count()
    active_tasks = Task.objects.filter(status='ONGOING').count()
    completed_tasks = Task.objects.filter(status='COMPLETED').count()
    team_members = User.objects.filter(role='EMPLOYEE').count()
    active_members = User.objects.filter(role='EMPLOYEE', is_active=True).count()
    
    # Get recent projects - using start_date or end_date instead of created_at
    recent_projects = Projects.objects.all().order_by('-start_date')[:5]  # or use '-end_date'
    
    # Get pending tasks
    pending_tasks = Task.objects.filter(status='PENDING').order_by('-created_at')[:5]
    
    # Get team members list
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
    }
    return render(request, 'teamlead_dashboard.html', context)

@login_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def employee_dashboard(request):
    user = request.user

    # Tasks assigned to employee
    tasks = Task.objects.filter(assigned_to=user)

    # Projects assigned to employee
    projects = Projects.objects.filter(assigned_to=user)

    return render(request, "employee_dashboard.html", {
        "tasks": tasks,
        "projects": projects
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
    ## for understanding
    # get_object_or_404() requires two arguments:
    # get_object_or_404(Model, condition)
    user = get_object_or_404(User,id=user_id)
    profile, created = UserProfile.objects.get_or_create(user=user) ## it automatically created profile if it is missed
    departments = Department.objects.all()
    designations = Designation.objects.all()

    if request.method == "POST":
        user.email = request.POST.get("email")
        user.username = request.POST.get("username")
        user.role = request.POST.get("role")
        user.save()

        # DROPDOWN LOGIC
        profile.department_id = request.POST.get("department")
        profile.designation_id = request.POST.get("designation")
        profile.employee_id = request.POST.get("employee_id")
        profile.phone = request.POST.get("phone")
        profile.date_of_joining = request.POST.get("date_of_joining")

        profile.save()

        messages.success(request, "User updated successfully")
        return redirect("admin_view_users")
    
    context = {
        "user": user,
        "profile": profile,
        "departments": departments,
        "designations": designations
    }

    return render(request, "edit_user.html",context)


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
    employees = User.objects.filter(role='EMPLOYEE')
    return render(request, 'teamlead_view_users.html', {'users': employees})

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
            # Save User first
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password1'])
            user.save()

            # Save profile
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()

            return redirect("admin_dashboard")
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
        if form.is_valid():
            # Step 1: Save the task instance but don't commit to DB yet
            task = form.save(commit=False)
            
            # Step 2: Set any additional fields if needed
            assigner = request.user
            
            # Step 3: Save the task to DB
            task.save()
            
            # Step 4: CRITICAL - Save ALL ManyToMany fields (assigned_to AND observers!)
            form.save_m2m()  # This saves BOTH assigned_to and observers relationships
            
            # Step 5: Create notifications for ALL assigned employees
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
            
            # Step 6: Create notifications for observers (if any)
            # Create a list of assignee names for the message
            assignee_names = ", ".join([u.get_full_name() or u.username for u in task.assigned_to.all()])
            
            for observer in task.observers.all():
                Notification.objects.create(
                    user=observer,
                    message=f'Task "{task.name}" has been assigned to {assignee_names}'
                )

            messages.success(request, f'Task "{task.name}" assigned successfully to {task.assigned_to.count()} employee(s) with {task.observers.count()} observer(s)!')
            return redirect("teamlead_dashboard")
        else:
            # Form is invalid, show errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
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

        if project_form.is_valid() and resource_formset.is_valid():
            project = project_form.save()

            for resource_form in resource_formset:
                if resource_form.cleaned_data:
                    resource = resource_form.save(commit=False)
                    resource.project = project
                    resource.save()

            if request.user.role.upper() == "ADMIN":
                return redirect("view_projects")
            else:
                return redirect("teamlead_dashboard")
    else:
        # This is the GET request: we need to define both forms here too!
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
    """Task dashboard showing all tasks in list view (Page 1)"""
    
    # Get tasks based on user role
    if request.user.role == "EMPLOYEE":
        # Employees see only their own tasks
        tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')
    else:
        # Admins and Team Leads see ALL tasks
        tasks = Task.objects.all().order_by('-created_at')
    
    # Statistics
    total_tasks = tasks.count()
    overdue_tasks = tasks.filter(
        status__in=['PENDING', 'ONGOING'],
        deadline__lt=timezone.now()
    ).count()
    
    # Add calculated fields for each task
    for task in tasks:
        # Format time tracking display
        if task.status == 'ONGOING' and task.start_time:
            elapsed = timezone.now() - task.start_time
            if task.total_paused_duration:
                elapsed = elapsed - task.total_paused_duration
            total_seconds = int(elapsed.total_seconds())
        elif task.status == 'COMPLETED' and task.total_time:
            total_seconds = int(task.total_time.total_seconds())
        else:
            total_seconds = 0
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        task.time_spent_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Format deadline display
        if task.deadline:
            if task.deadline.date() == timezone.now().date():
                task.deadline_display = f"Today, {task.deadline.strftime('%H:%M')}"
            else:
                task.deadline_display = task.deadline.strftime('%b %d, %H:%M')
        else:
            task.deadline_display = "No deadline"
        
        # Format created date
        task.created_display = task.created_at.strftime('%b %d, %H:%M')
        
        # Estimated time (default 04:00)
        task.estimated_display = "04:00"
    
    context = {
        'tasks': tasks,
        'total_tasks': total_tasks,
        'overdue_tasks': overdue_tasks,
        'selected_count': 0,
        'user_role': request.user.role,  # Optional: pass role to template
    }
    return render(request, 'task_dashboard.html', context)


## TaskSummary 
@login_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def add_task_summary(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)
    
    # Optional: Check if task is in correct state
    if task.status != "ONGOING":
        messages.error(request, "You can only add summary to ongoing tasks.")
        return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")
    
    if request.method == 'POST':
        summary = request.POST.get('summary')
        if summary and summary.strip():  # Check if summary is not empty
            task.summary = summary.strip()
            task.save()
            messages.success(request, "Summary added successfully! You can now complete the task.")
            # Redirect back to task detail
            return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")
        else:
            messages.error(request, "Please enter a valid summary.")
    
    return render(request, 'add_task_summary.html', {'task': task})





import math
## employee task
@login_required
@allowed_roles(allowed_roles=["EMPLOYEE", "TEAM_LEAD", "ADMIN"])
def employee_tasks(request):
    task_id = request.GET.get('task_id')
    employee_id = request.GET.get('employee_id')  # Add this for team lead view
    
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
            'viewing_employee': employee  # Optional: pass employee info to template
        })
    
    # Case 2: Viewing single task by ID
    elif task_id:
        task = get_object_or_404(Task, id=task_id)
        
        # Permission check: Employee can only view their own tasks
        if request.user.role == "EMPLOYEE" and task.assigned_to != request.user:
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
import datetime
@login_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def start_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    # Check if task can be started
    if task.status != "PENDING":
        messages.error(request, f'Task cannot be started because it is {task.get_status_display()}.')
        return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")  # FIXED

    # COMPLETELY RESET the task for fresh start
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
    messages.success(request, f'Task "{task.name}" started successfully!')
    return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")

## pause task
from django.urls import reverse
@login_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def pause_task(request, task_id):
    """Pause an ongoing task - records the pause time"""
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    # Check if task can be paused
    if task.status != "ONGOING":
        messages.error(request, 'Only ongoing tasks can be paused.')
        # FIX: Redirect back to the same task detail page
        return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")

    # Check if task is already paused
    if task.paused_time is not None:
        messages.error(request, 'Task is already paused.')
        # FIX: Redirect back to the same task detail page
        return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")

    # Pause the task
    task.paused_time = timezone.now()
    task.save()

    messages.info(request, f'Task "{task.name}" paused.')
    # FIX: Redirect back to the same task detail page
    return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")

## Resume task
def resume_task(request, task_id):
    """Resume a paused task - calculates paused duration and clears pause time"""
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    # Check if task is paused
    if task.status != "ONGOING" or task.paused_time is None:
        messages.error(request, 'Task is not paused.')
        return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")  # FIXED

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

    messages.success(request, f'Task "{task.name}" resumed.')
    return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")


## complete task
@login_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def complete_task(request, task_id):
    """Complete a task - calculates total time spent and marks as COMPLETED"""
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    # Check if task can be completed
    if task.status == "COMPLETED":
        messages.error(request, 'Task is already completed.')
        return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")  # FIXED

    # IMPORTANT: Check if summary exists
    if not task.summary:
        messages.error(request, 'Please add a task summary before completing.')
        return redirect('add_task_summary', task_id=task.id)


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

    messages.success(request, f'Task "{task.name}" completed! Total time: {time_display}')
    return redirect(f"{reverse('employee_tasks')}?task_id={task.id}")

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

## home page
def home(request):
    return render(request, "home.html")

