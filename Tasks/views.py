# ============================================================================
# STANDARD LIBRARY IMPORTS
# ============================================================================
import json
import datetime
# ============================================================================
# DJANGO CORE IMPORTS
# ============================================================================
from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
# ============================================================================
# PROJECT APP IMPORTS
# ============================================================================
from projects.models import Projects
from .models import Task
from .forms import TaskForm
from users.models import User, ActivityLog
from notifications.models import Notification
from users.permissions import has_any
from users.decorators import jwt_or_session_required, permission_required
from users.permissions import (
    can_add_task,          
    can_change_task,       
    can_delete_task,        
    can_view_task,          
    can_manage_all_tasks,   
    can_start_task,         
    can_resume_task,        
    can_complete_task,      
    is_manager_like,        
    get_task_queryset,      
    get_projects_queryset,  
    dashboard_url_for,
    can_view_all_projects,      
)


@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def edit_task(request, task_id):
    """Render edit form - submission handled by API"""
    
    task = get_object_or_404(Task, id=task_id)
    
    # Ownership check
    is_task_owner = task.assigned_by.filter(id=request.user.id).exists()
    is_project_creator = task.project.created_by == request.user
    is_admin_override = request.user.is_superuser
    
    if not (is_task_owner or is_project_creator or is_admin_override):
        messages.error(request, 'Only task owner or project creator can edit this task')
        return redirect('view_project_detail', project_id=task.project.id)
    
    # Create form with filtered querysets
    class FilteredTaskForm(TaskForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if can_view_all_projects(request.user):
                self.fields['project'].queryset = Projects.objects.all()
            else:
                self.fields['project'].queryset = Projects.objects.filter(assigned_to=request.user)
            
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
            
            self.fields['observers'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
            
            self.fields['assigned_by'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
    
    form = FilteredTaskForm(instance=task)
    
    # Just render the HTML form
    return render(request, 'edit_task.html', {
        'form': form,
        'task': task,
        'is_edit': True
    })


@jwt_or_session_required
@permission_required('Tasks.add_task')
@csrf_exempt
def assign_task(request):
    """Render assign task form - submission handled by API"""
    
    class FilteredTaskForm(TaskForm):
        def __init__(self, user, *args, **kwargs): 
            super().__init__(*args, **kwargs)
            if can_view_all_projects(user):  
                self.fields['project'].queryset = Projects.objects.all()
            else:
                self.fields['project'].queryset = Projects.objects.filter(assigned_to=user)
            
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
            
            self.fields['observers'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
            
            self.fields['assigned_by'].queryset = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True)
    
    
    project_id = request.GET.get('project')
    initial_data = {}
    project = None
    
    if project_id:
        initial_data['project'] = project_id
        try:
            project = Projects.objects.get(id=project_id)
        except (Projects.DoesNotExist, ValueError):
            pass
    
    form = FilteredTaskForm(request.user, initial=initial_data)
    
    return render(request, "assign_task.html", {
        "form": form,
        "preselected_project": project
    })


@jwt_or_session_required
@permission_required('Tasks.view_task')
def task_dashboard(request):
    
    return render(request, 'task_dashboard.html', {
        'can_change_task': request.user.has_perm('Tasks.change_task'),
        'can_delete_task': request.user.has_perm('Tasks.delete_task'),
        'can_add_task': request.user.has_perm('Tasks.add_task'),
    })


@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def add_task_summary(request, task_id):
  
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
    
   
    if task.status != "ONGOING":
        return JsonResponse({
            'success': False,
            'error': 'You can only add summary to ongoing tasks.'
        }, status=400)
    
    if request.method == 'POST':
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
    
    return render(request, 'add_task_summary.html', {'task': task})


@jwt_or_session_required
@permission_required('Tasks.view_task')
def employee_tasks(request):
    """Employee tasks view - renders HTML shell, data loaded via API"""
    
    task_id = request.GET.get('task_id')
    employee_id = request.GET.get('employee_id')
    
    # Just render the HTML template - no data logic
    return render(request, "employee_tasks.html", {
        'task_id': task_id,
        'viewing_employee_id': employee_id,
    })


@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def start_task(request, task_id):
    """Start a task - AJAX enabled"""
    
    if can_manage_all_tasks(request.user):
        task = get_object_or_404(Task, id=task_id)
    else:
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    if task.status != "PENDING":
        return JsonResponse({
            'success': False,
            'error': f'Task cannot be started because it is {task.get_status_display()}.'
        }, status=400)

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


@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def pause_task(request, task_id):
    """Pause an ongoing task - AJAX enabled"""
    
    if can_manage_all_tasks(request.user):
        task = get_object_or_404(Task, id=task_id)
    else:
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    if task.status != "ONGOING":
        return JsonResponse({
            'success': False,
            'error': 'Only ongoing tasks can be paused.'
        }, status=400)

    if task.paused_time is not None:
        return JsonResponse({
            'success': False,
            'error': 'Task is already paused.'
        }, status=400)

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


@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def resume_task(request, task_id):
    """Resume a paused task - AJAX enabled"""
    
    if can_manage_all_tasks(request.user):
        task = get_object_or_404(Task, id=task_id)
    else:
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    if task.status != "ONGOING" or task.paused_time is None:
        return JsonResponse({
            'success': False,
            'error': 'Task is not paused.'
        }, status=400)

    paused_duration = timezone.now() - task.paused_time

    if task.total_paused_duration:
        task.total_paused_duration += paused_duration
    else:
        task.total_paused_duration = paused_duration

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


@jwt_or_session_required
@permission_required('Tasks.change_task')
@csrf_exempt
def complete_task(request, task_id):
    """Complete a task - AJAX enabled with JSON response"""
    
    if can_manage_all_tasks(request.user):
        task = get_object_or_404(Task, id=task_id)
    else:
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    if task.status == "COMPLETED":
        return JsonResponse({
            'success': False,
            'error': 'Task is already completed.'
        }, status=400)

    if not task.summary:
        return JsonResponse({
            'success': False,
            'error': 'Please add a task summary before completing.',
            'redirect_url': reverse('add_task_summary', args=[task.id])
        }, status=400)

    if task.status == "ONGOING" and task.start_time:
        if task.paused_time:
            paused_duration = timezone.now() - task.paused_time
            if task.total_paused_duration:
                task.total_paused_duration += paused_duration
            else:
                task.total_paused_duration = paused_duration
            task.paused_time = None

        total_spent = timezone.now() - task.start_time
        if task.total_paused_duration:
            total_spent = total_spent - task.total_paused_duration

        task.total_time = total_spent
        task.end_time = timezone.now()

    task.status = "COMPLETED"
    task.save()

    time_display = "00:00:00"
    if task.total_time:
        total_seconds = int(task.total_time.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    employee_name = request.user.get_full_name() or request.user.username
    message = f"Task '{task.name}' has been completed by {employee_name}. Time spent: {time_display}"
    
    users_to_notify = set()
    
    for user in User.objects.filter(is_active=True):
        if is_manager_like(user):
            users_to_notify.add(user)
    
    for admin in User.objects.filter(role='ADMIN', is_active=True):
        users_to_notify.add(admin)
    
    if task.project and task.project.created_by:
        users_to_notify.add(task.project.created_by)
    
    for user in users_to_notify:
        Notification.objects.create(user=user, message=message, content_object=task)

    return JsonResponse({
        'success': True,
        'message': f'Task "{task.name}" completed! Total time: {time_display}',
        'task_id': task.id,
        'time_display': time_display,
        'status': 'COMPLETED'
    })

