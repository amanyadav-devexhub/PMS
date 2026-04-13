# ============================================================================
# STANDARD LIBRARY IMPORTS
# ============================================================================

import json
# Used for: Parsing JSON request body in add_task_summary()

import datetime
# Used for: Creating timedelta objects in start_task() for total_paused_duration

# ============================================================================
# DJANGO CORE IMPORTS
# ============================================================================

from django.db import models
# Used for: Complex Q queries in task_dashboard (models.Q filtering)

from django.shortcuts import render, get_object_or_404, redirect
# render: Returning HTML templates throughout
# get_object_or_404: Safe task retrieval throughout
# redirect: URL redirections throughout

from django.http import JsonResponse
# Used for: All AJAX endpoints returning JSON (edit_task, delete_task, assign_task, etc.)

from django.views.decorators.csrf import csrf_exempt
# Used for: All AJAX POST endpoints to disable CSRF for JWT auth

from django.urls import reverse
# Used for: Building redirect URLs in assign_task(), complete_task()

from django.utils import timezone
# Used for: Time calculations in task_dashboard, employee_tasks, start_task, pause_task, resume_task, complete_task

from django.db.models import Q
# Used for: Complex OR queries in task_dashboard for search functionality

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# Used for: Pagination in task_dashboard

from django.contrib import messages
# Used for: User feedback messages in edit_task, delete_task, employee_tasks

# ============================================================================
# PROJECT APP IMPORTS
# ============================================================================

from projects.models import Projects
# Used for: Project filtering in edit_task and assign_task forms

from .models import Task
# Used for: Task CRUD operations throughout all views

from .forms import TaskForm
# Used for: Creating/Editing tasks in assign_task and edit_task

from users.models import User, ActivityLog
# User: Getting user lists for assignee/observer fields
# ActivityLog: Logging task creation, deletion, restoration

from notifications.models import Notification
# Used for: Sending notifications for task assignment, start, pause, resume, completion

from users.permissions import has_any
# Used for: Checking view_all_tasks permission in employee_tasks

from users.decorators import jwt_or_session_required, permission_required
# jwt_or_session_required: JWT authentication for all protected views
# permission_required: Permission checking for role-based access

from users.permissions import (
    can_add_task,           # Used in assign_task permission check
    can_change_task,        # Used in edit_task, start_task, pause_task, resume_task, complete_task
    can_delete_task,        # Used in delete_task permission check
    can_view_task,          # Used in task_dashboard, employee_tasks permission check
    can_manage_all_tasks,   # Used for admin override in task operations
    can_start_task,         # Permission check for start button visibility
    can_resume_task,        # Permission check for resume button visibility
    can_complete_task,      # Permission check for complete button visibility
    is_manager_like,        # Used in employee_tasks for manager-specific views
    get_task_queryset,      # Used in task_dashboard for permission-filtered tasks
    get_projects_queryset,  # Used for project filtering in forms
    dashboard_url_for,
    can_view_all_projects,      # Used for default redirect URLs
)




# Create your views here.

# edit task - AJAX enabled with ownership check
@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def edit_task(request, task_id):
    """Edit Task - AJAX enabled"""
    
    task = get_object_or_404(Task, id=task_id)

    # 🔒 OWNERSHIP CHECK: Task owner OR project creator can edit
    is_task_owner = task.assigned_by.filter(id=request.user.id).exists()
    is_project_creator = task.project.created_by == request.user
    is_admin_override = request.user.is_superuser
    
    if not (is_task_owner or is_project_creator or is_admin_override):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Only task owner or project creator can edit this task'
            }, status=403)
        messages.error(request, 'Only task owner or project creator can edit this task')
        return redirect('view_project_detail', project_id=task.project.id)
    
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
                    'message': f'Task "{task.name}" updated successfully!',
                    'task_id': task.id,
                    'task_name': task.name,
                    'project_id': task.project.id
                })
            else:
                messages.success(request, f'Task "{task.name}" updated successfully!')
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


## delete task - soft delete with ownership check
@jwt_or_session_required
@permission_required('Tasks.delete_task')
@csrf_exempt
def delete_task(request, task_id):
    """Delete a task - Soft delete with ownership check"""
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    task = get_object_or_404(Task, id=task_id)
    project_id = task.project.id
    task_name = task.name
    
    # Only allow POST requests
    if request.method != 'POST':
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
        context = {'task': task}
        return render(request, 'delete_task_confirm.html', context)
    
    # 🔒 OWNERSHIP CHECK: Task owner OR Project creator can delete
    is_task_owner = task.assigned_by.filter(id=request.user.id).exists()
    is_project_creator = task.project.created_by == request.user
    
    if not (is_task_owner or is_project_creator):
        error_msg = "Only task owner or project creator can delete this task"
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg}, status=403)
        messages.error(request, error_msg)
        return redirect('view_project_detail', project_id=project_id)
    
    # ✅ SOFT DELETE
    from django.utils import timezone
    task.is_deleted = True
    task.deleted_at = timezone.now()
    task.save()
    
    # 📝 LOG TO ACTIVITY LOG
    from users.models import ActivityLog
    ActivityLog.objects.create(
        user=request.user,
        action='deleted',
        entity_type='task',
        entity_id=task.id,
        entity_name=task.name
    )
    
    # Return success response
    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': f'Task "{task_name}" moved to trash successfully!',
            'project_id': project_id
        })
    else:
        messages.success(request, f'Task "{task_name}" moved to trash successfully!')
        return redirect('view_project_detail', project_id=project_id)



## assign task - AJAX enabled with project-based filtering and ownership check
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

            task.created_by = request.user
            
            # Step 2: Get estimated time from the hidden field
            estimated_time = request.POST.get('estimated_time')
            if estimated_time:
                task.estimated_time = int(estimated_time)
            
            # Step 3: Get selected task owners
            assigned_by_ids = request.POST.getlist('assigned_by')
            
            # Step 4: Save the task to DB (need ID before setting ManyToMany)
            task.save()



            # 📝 LOG TO ACTIVITY LOG - TASK CREATED
            from users.models import ActivityLog
            ActivityLog.objects.create(
                user=request.user,
                action='created',
                entity_type='task',
                entity_id=task.id,
                entity_name=task.name
            )
            
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
                        message=f'Task "{task.name}" has been assigned to you',
                        content_object=task
                    )
            
            # Step 8: Create notifications for observers
            assignee_names = ", ".join([u.get_full_name() or u.username for u in task.assigned_to.all()])
            for observer in task.observers.all():
                Notification.objects.create(
                    user=observer,
                    message=f'Task "{task.name}" has been assigned to {assignee_names}',
                    content_object=task
                )

            # Format estimated time for success message
            hours = task.estimated_time // 3600
            minutes = (task.estimated_time % 3600) // 60
            time_display = f"{hours} hour{'s' if hours != 1 else ''}"
            if minutes > 0:
                time_display += f" {minutes} minute{'s' if minutes != 1 else ''}"

            # Construct the redirect URL with task_id
            redirect_url = reverse('employee_tasks') + f'?task_id={task.id}'

            # AJAX response
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': f'Task "{task.name}" assigned successfully to {task.assigned_to.count()} employee(s)!',
                    'task_id': task.id,
                    'task_name': task.name,
                    'time_display': time_display,
                    'redirect_url': redirect_url,
                })
            else:
                # Regular form submission fallback
                messages.success(request, f'Task "{task.name}" assigned successfully to {task.assigned_to.count()} employee(s)!')
                return redirect(redirect_url)
        else:
            # Form is invalid
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
            else:
                # Re-fetch project for context if needed
                project_id = request.POST.get('project')
                project = None
                if project_id:
                    try:
                        project = Projects.objects.get(id=project_id)
                    except (Projects.DoesNotExist, ValueError):
                        pass
                context = {'form': form, 'preselected_project': project}
                return render(request, "assign_task.html", context)
    
    # GET request - show form (pre-populated if project_id is in URL)
    else:
        project_id = request.GET.get('project')
        initial_data = {}
        project = None
        if project_id:
            initial_data['project'] = project_id
            try:
                project = Projects.objects.get(id=project_id)
            except (Projects.DoesNotExist, ValueError):
                pass
            
        form = FilteredTaskForm(initial=initial_data)

    return render(request, "assign_task.html", {"form": form, "preselected_project": project})


## task dashboard - AJAX enabled with search and pagination
@jwt_or_session_required
@permission_required('Tasks.view_task')
def task_dashboard(request):
    """Task dashboard showing all tasks in list view"""
    
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get pagination parameters
        page = request.GET.get("page", 1)
        page_size = request.GET.get("page_size", 10)
        search = request.GET.get("search", "").strip()
        
        # Use centralized permission-filtered queryset
        tasks = get_task_queryset(request.user)

        if search:
            tasks = tasks.filter(
                models.Q(name__icontains=search) |
                models.Q(description__icontains=search) |
                models.Q(assigned_to__username__icontains=search) |
                models.Q(assigned_to__first_name__icontains=search) |
                models.Q(assigned_to__last_name__icontains=search) |
                models.Q(project__name__icontains=search)
            ).distinct()
        
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
            
            # Get assignees with details
            assigned_to_details = []
            for assignee in task.assigned_to.all():
                assigned_to_details.append({
                    'id': assignee.id,
                    'full_name': assignee.get_full_name() or assignee.username
                })
            
            tasks_data.append({
                'id': task.id,
                'name': task.name,
                'status': task.status,
                'status_display': task.get_status_display(),
                'time_spent_display': time_spent_display,
                'estimated_display': estimated_display,
                'is_overdue': is_overdue,
                'deadline': task.deadline.strftime('%b %d, %H:%M') if task.deadline else None,
                'project': task.project.id,
                'project_name': task.project.name[:15] if task.project.name else 'N/A',
                'assigned_to_details': assigned_to_details,
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
    tasks = get_task_queryset(request.user)

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
                            is_read=False,
                            content_object=task
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
                            is_read=False,
                            content_object=task
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
                            is_read=False,
                            content_object=task
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
        'can_change_task': request.user.has_perm('Tasks.change_task'),
    }
    return render(request, 'task_dashboard.html', context)


# ============================================================================
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


# ## employee task view - AJAX enabled with permission checks and calculated fields
# @jwt_or_session_required
# @permission_required('Tasks.view_task')
# def employee_tasks(request):
#     task_id = request.GET.get('task_id')
#     employee_id = request.GET.get('employee_id')
    
#     # Helper function to check view_all_tasks permission
#     def has_view_all_tasks(user):
#         return has_any(user, ['Tasks.view_all_tasks', 'tasks.view_all_tasks'])
    
#     # Handle AJAX request - return JSON
#     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#         # Case 1: Manager viewing specific employee's tasks
#         if employee_id and is_manager_like(request.user):
#             employee = get_object_or_404(User, id=employee_id)
#             tasks = Task.objects.filter(assigned_to=employee).order_by('-created_at')
            
#             tasks_data = []
#             for task in tasks:
#                 tasks_data.append({
#                     'id': task.id,
#                     'name': task.name,
#                     'status': task.status,
#                     'status_display': task.get_status_display(),
#                 })
            
#             return JsonResponse({
#                 'success': True,
#                 'tasks': tasks_data,
#                 'viewing_employee': employee.get_full_name() or employee.username,
#                 'total_tasks': len(tasks_data)
#             })
        
#         # Case 2: Viewing single task by ID - FIXED PERMISSION CHECK
#         elif task_id:
#             task = get_object_or_404(Task, id=task_id)
            
#             # Check permission: view_all_tasks OR assigned to task OR can_manage_all_tasks
#             if not (has_view_all_tasks(request.user) or task.assigned_to.filter(id=request.user.id).exists() or can_manage_all_tasks(request.user)):
#                 return JsonResponse({
#                     'success': False, 
#                     'error': "You don't have permission to view this task."
#                 }, status=403)
            
#             return JsonResponse({
#                 'success': True,
#                 'task': {
#                     'id': task.id,
#                     'name': task.name,
#                     'description': task.description,
#                     'status': task.status,
#                     'status_display': task.get_status_display(),
#                     'summary': task.summary,
#                 }
#             })
        
#         # Case 3: Employee viewing their own tasks list
#         else:
#             tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')
#             tasks_data = [{'id': t.id, 'name': t.name, 'status': t.status, 'status_display': t.get_status_display()} for t in tasks]
#             return JsonResponse({'success': True, 'tasks': tasks_data, 'total_tasks': len(tasks_data)})
    
#     # ========== YOUR ORIGINAL CODE BELOW - COMPLETELY UNCHANGED ==========
#     # Case 1: Manager viewing specific employee's tasks
#     if employee_id and is_manager_like(request.user):
#         employee = get_object_or_404(User, id=employee_id)
#         tasks = Task.objects.filter(assigned_to=employee).order_by('-created_at')
        
#         # Add calculated fields for each task
#         for task in tasks:
#             if task.estimated_time:
#                 hours = task.estimated_time // 3600
#                 minutes = (task.estimated_time % 3600) // 60
#                 task.estimated_display = f"{hours:02d}:{minutes:02d}:00"
#             else:
#                 task.estimated_display = "01:00:00"
            
#             if task.status == "ONGOING" and task.start_time:
#                 elapsed = timezone.now() - task.start_time
#                 if task.total_paused_duration:
#                     elapsed = elapsed - task.total_paused_duration
#                 if task.paused_time:
#                     current_pause = timezone.now() - task.paused_time
#                     elapsed = elapsed - current_pause
                
#                 total_seconds = int(elapsed.total_seconds())
#                 hours = total_seconds // 3600
#                 minutes = (total_seconds % 3600) // 60
#                 seconds = total_seconds % 60
#                 task.current_display_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
#             elif task.status == "COMPLETED" and task.total_time:
#                 total_seconds = int(task.total_time.total_seconds())
#                 hours = total_seconds // 3600
#                 minutes = (total_seconds % 3600) // 60
#                 seconds = total_seconds % 60
#                 task.total_time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
#         return render(request, "employee_tasks.html", {
#             'tasks': tasks,
#             'current_time': timezone.now(),
#             'viewing_employee': employee
#         })
    
#     # Case 2: Viewing single task by ID - FIXED PERMISSION CHECK
#     elif task_id:
#         task = get_object_or_404(Task, id=task_id)
        
#         # Check permission: view_all_tasks OR assigned to task OR observing task OR can_manage_all_tasks
#         if not (has_view_all_tasks(request.user) or 
#                 task.assigned_to.filter(id=request.user.id).exists() or 
#                 task.observers.filter(id=request.user.id).exists() or
#                 can_manage_all_tasks(request.user)):
#             messages.error(request, "You don't have permission to view this task.")
#             return redirect('task_dashboard')
        
#         tasks = [task]
        
#         # Format estimated time for display
#         if task.estimated_time:
#             hours = task.estimated_time // 3600
#             minutes = (task.estimated_time % 3600) // 60
#             task.estimated_display = f"{hours:02d}:{minutes:02d}:00"
#         else:
#             task.estimated_display = "01:00:00"
        
#         # Calculate current time for ongoing tasks
#         if task.status == "ONGOING" and task.start_time:
#             elapsed = timezone.now() - task.start_time
#             if task.total_paused_duration:
#                 elapsed = elapsed - task.total_paused_duration
#             if task.paused_time:
#                 current_pause = timezone.now() - task.paused_time
#                 elapsed = elapsed - current_pause
            
#             total_seconds = int(elapsed.total_seconds())
#             hours = total_seconds // 3600
#             minutes = (total_seconds % 3600) // 60
#             seconds = total_seconds % 60
#             task.current_display_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
#         # Format completed task time
#         elif task.status == "COMPLETED" and task.total_time:
#             total_seconds = int(task.total_time.total_seconds())
#             hours = total_seconds // 3600
#             minutes = (total_seconds % 3600) // 60
#             seconds = total_seconds % 60
#             task.total_time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
#     # Case 3: Employee viewing their own tasks list
#     else:
#         tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')
#         for task in tasks:
#             if task.estimated_time:
#                 hours = task.estimated_time // 3600
#                 minutes = (task.estimated_time % 3600) // 60
#                 task.estimated_display = f"{hours:02d}:{minutes:02d}:00"
    
#     return render(request, "employee_tasks.html", {
#         'tasks': tasks,
#         'current_time': timezone.now()
#     })


@jwt_or_session_required
@permission_required('Tasks.view_task')
def employee_tasks(request):
    task_id = request.GET.get('task_id')
    employee_id = request.GET.get('employee_id')
    
    # Helper function to check view_all_tasks permission
    def has_view_all_tasks(user):
        return has_any(user, ['Tasks.view_all_tasks', 'tasks.view_all_tasks'])
    
    # ========== AJAX REQUEST - Return JSON ==========
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        
        # Case 1: Manager viewing specific employee's tasks
        if employee_id and is_manager_like(request.user):
            employee = get_object_or_404(User, id=employee_id)
            tasks = Task.objects.filter(assigned_to=employee, is_deleted=False).order_by('-created_at')
            
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
        
        # Case 2: Viewing single task by ID - Return JSON data
        elif task_id:
            task = get_object_or_404(Task, id=task_id, is_deleted=False)
            
            # Check permission
            if not (has_view_all_tasks(request.user) or 
                    task.assigned_to.filter(id=request.user.id).exists() or 
                    can_manage_all_tasks(request.user)):
                return JsonResponse({
                    'success': False, 
                    'error': "You don't have permission to view this task."
                }, status=403)
            
            # Calculate display values
            estimated_display = "01:00:00"
            if task.estimated_time:
                hours = task.estimated_time // 3600
                minutes = (task.estimated_time % 3600) // 60
                estimated_display = f"{hours:02d}:{minutes:02d}:00"
            
            current_display_time = "00:00:00"
            total_time_display = "00:00:00"
            is_paused = False
            
            if task.status == "ONGOING" and task.start_time:
                elapsed = timezone.now() - task.start_time
                if task.total_paused_duration:
                    elapsed = elapsed - task.total_paused_duration
                if task.paused_time:
                    is_paused = True
                    current_pause = timezone.now() - task.paused_time
                    elapsed = elapsed - current_pause
                total_seconds = int(elapsed.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                current_display_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            elif task.status == "COMPLETED" and task.total_time:
                total_seconds = int(task.total_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                total_time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            return JsonResponse({
                'success': True,
                'task': {
                    'id': task.id,
                    'name': task.name,
                    'description': task.description,
                    'status': task.status,
                    'status_display': task.get_status_display(),
                    'summary': task.summary,
                    'estimated_display': estimated_display,
                    'current_display_time': current_display_time,
                    'total_time_display': total_time_display,
                    'is_paused': is_paused,
                    'created_at': task.created_at.strftime("%B %d, %Y %H:%M"),
                    'deadline': task.deadline.strftime("%B %d, %Y %H:%M") if task.deadline else None,
                    'end_date': task.end_date.strftime("%B %d, %Y") if task.end_date else None,
                    'assigned_to': [
                        {
                            'id': user.id,
                            'name': user.get_full_name() or user.username,
                            'email': user.email
                        } for user in task.assigned_to.all()
                    ],
                    'assigned_by': [
                        {
                            'id': user.id,
                            'name': user.get_full_name() or user.username,
                            'email': user.email
                        } for user in task.assigned_by.all()
                    ],
                    'observers': [
                        {
                            'id': user.id,
                            'name': user.get_full_name() or user.username,
                            'email': user.email
                        } for user in task.observers.all()
                    ],
                    'project': {
                        'id': task.project.id if task.project else None,
                        'name': task.project.name if task.project else "No Project"
                    }
                }
            })
        
        # Case 3: Employee viewing their own tasks list
        else:
            tasks = Task.objects.filter(assigned_to=request.user, is_deleted=False).order_by('-created_at')
            tasks_data = [{
                'id': t.id, 
                'name': t.name, 
                'status': t.status, 
                'status_display': t.get_status_display()
            } for t in tasks]
            return JsonResponse({
                'success': True, 
                'tasks': tasks_data, 
                'total_tasks': len(tasks_data)
            })
    
    # ========== REGULAR REQUEST - Return HTML skeleton ==========
    
    # Case 1: Manager viewing specific employee's tasks
    if employee_id and is_manager_like(request.user):
        employee = get_object_or_404(User, id=employee_id)
        return render(request, "employee_tasks.html", {
            'viewing_employee': employee,
            'task_id': None,
            'is_ajax_mode': True
        })
    
    # Case 2: Viewing single task by ID - Return HTML skeleton
    elif task_id:
        task = get_object_or_404(Task, id=task_id)
        
        # Check permission
        if not (has_view_all_tasks(request.user) or 
                task.assigned_to.filter(id=request.user.id).exists() or 
                task.observers.filter(id=request.user.id).exists() or
                can_manage_all_tasks(request.user)):
            messages.error(request, "You don't have permission to view this task.")
            return redirect('task_dashboard')
        
        return render(request, "employee_tasks.html", {
            'task_id': task_id,
            'viewing_employee': None,
            'is_ajax_mode': True
        })
    
    # Case 3: Employee viewing their own tasks list
    else:
        return render(request, "employee_tasks.html", {
            'task_id': None,
            'viewing_employee': None,
            'is_ajax_mode': True
        })


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
            message=f"▶️ Task '{task.name}' has been started by {request.user.get_full_name() or request.user.username}",
            content_object=task
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
            message=f"⏸️ Task '{task.name}' has been paused by {request.user.get_full_name() or request.user.username}",
            content_object=task
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
            message=f"▶️ Task '{task.name}' has been resumed by {request.user.get_full_name() or request.user.username}",
            content_object=task
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
        Notification.objects.create(user=user, message=message, content_object=task)

    # Return JSON response instead of redirect
    return JsonResponse({
        'success': True,
        'message': f'Task "{task.name}" completed! Total time: {time_display}',
        'task_id': task.id,
        'time_display': time_display,
        'status': 'COMPLETED'
    })

