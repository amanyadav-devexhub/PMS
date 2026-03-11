

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

# ## view_project_details
@login_required
@allowed_roles(allowed_roles=["ADMIN", "TEAM_LEAD","EMPLOYEE"])
def view_project_detail(request, project_id):
    project = get_object_or_404(Projects, id=project_id)
    resources = project.resources.all()

    return render(
        request,
        "view_project_detail.html",
        {
            "project": project,
            "resources": resources
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
    users = User.objects.all()  # Get all users from the database
    return render(request, "admin_dashboard.html", {"users": users})

@login_required
@allowed_roles(allowed_roles=["TEAM_LEAD"])
def teamlead_dashboard(request):
    return render(request, "teamlead_dashboard.html")


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
@allowed_roles(allowed_roles=["TEAM_LEAD"])
def assign_task(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            # Step 1: Save the task instance
            task = form.save(commit=False)  # Don't save to DB yet
            
            # Step 2: Assign the employee from the form
            assigned_employee = task.assigned_to  # Assuming you have this field in Task model
            
            task.save()  # Now save the task
            assigner = request.user  # Who created the task
            
            # Step 3: Create a notification for the assigned employee
            from notifications.models import Notification
            if not Notification.objects.filter(user=assigned_employee, message=f'Task "{task.name}" has been assigned to you').exists():
                Notification.objects.create(
                    user=assigned_employee,
                    message=f'Task "{task.name}" has been assigned to you'
                )
            
            # Optional Step 4: Create notifications for observers (like TL/Admin)
            # if task.project and task.project.observers.exists():  # if you track observers in Project
            #     for observer in task.project.observers.all():
            #         Notification.objects.create(
            #             user=observer,
            #             message=f'Task "{task.name}" has been assigned to {assigned_employee.username}'
            #         )

        return redirect("teamlead_dashboard")
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

## employee task
@login_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def employee_tasks(request):
    # Get tasks assigned to logged-in employee
    tasks = Task.objects.filter(assigned_to=request.user)
    return render(request, "employee_tasks.html", {"tasks": tasks})

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
login_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def start_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    if task.status == "PENDING":
        task.status = "ONGOING"
        task.start_time = timezone.now()
        task.save()

        # Notify the task creator (assignee implicitly knows who created)
        # Notify all Admins and Team Leads
        observers = User.objects.filter(role__in=["ADMIN", "TEAM_LEAD"])
        message = f"Task '{task.name}' has been started by {request.user.username}."
        for user in observers:
            Notification.objects.create(user=user, message=message)

    return redirect("employee_tasks")

## complete task
@login_required
@allowed_roles(allowed_roles=["EMPLOYEE"])
def complete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    if task.status == "ONGOING" and task.start_time:
        task.end_time = timezone.now()
        task.total_time = task.end_time - task.start_time
        task.status = "COMPLETED"
        task.save()

        # Notify the assigner (same logic as above)
        # Notify all Admins and Team Leads
        observers = User.objects.filter(role__in=["ADMIN", "TEAM_LEAD"])
        message = f"Task '{task.name}' has been completed by {request.user.username}."
        for user in observers:
            Notification.objects.create(user=user, message=message)

    return redirect("employee_tasks")

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

