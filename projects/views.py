from django.shortcuts import render, get_object_or_404, redirect  # ← Keep only one
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.template.loader import render_to_string

from notifications.models import Notification  # ← Remove duplicate
from projects.models import Projects, ProjectResource
from Tasks.models import Task
from .forms import ProjectForm, ProjectResourceForm, ProjectResourceFormSet
from users.models import User
from users.decorators import jwt_or_session_required, permission_required
from users.permissions import (  # ← Fix this import
    can_view_all_projects,
    can_manage_users,
    is_manager_like,
    can_change_projects,
    dashboard_url_for,
    get_task_queryset,
    get_projects_queryset,  # ← This comes from users.permissions, not projects.permissions
)


# Create your views here.


## View Projects
@jwt_or_session_required
@permission_required('projects.view_projects')
def view_projects(request):
    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get("search", "").strip()
        page = request.GET.get("page", 1)
        page_size = request.GET.get("page_size", 10)
        
        from .permissions import get_projects_queryset
        projects = get_projects_queryset(request.user)

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
    
    # 🔽 ADD is_deleted=False filter
    if can_view_all_projects(request.user):
        projects = Projects.objects.filter(is_deleted=False)  # ← CHANGED
    else:
        projects = Projects.objects.filter(assigned_to=request.user, is_deleted=False)  # ← CHANGED

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




@jwt_or_session_required
@permission_required('projects.change_projects')
@csrf_exempt
def edit_projects(request, project_id):
    project = get_object_or_404(Projects, id=project_id)

    # 🔒 OWNERSHIP CHECK: Only project creator can edit
    if project.created_by != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Only the project creator can edit this project'
            }, status=403)
        messages.error(request, 'Only the project creator can edit this project')
        return redirect('view_projects')
    
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
@permission_required('projects.view_projects')
def view_project_detail(request, project_id):
    project = get_object_or_404(Projects, id=project_id, is_deleted=False)
    
    # Scoped users can only access projects assigned to them.
    if not can_view_all_projects(request.user) and request.user not in project.assigned_to.all():
        messages.error(request, "You don't have permission to view this project.")
        return redirect('view_projects')
    
    # Handle AJAX request for tasks pagination
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        tasks_page = request.GET.get('tasks_page', 1)
        tasks_page_size = request.GET.get('tasks_page_size', 10)
        
        tasks = get_task_queryset(request.user, queryset=Task.objects.filter(project=project))
        
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
    tasks = get_task_queryset(request.user, queryset=Task.objects.filter(project=project))
    
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




@jwt_or_session_required
@permission_required('projects.delete_projects')
@csrf_exempt
def delete_project(request, id):
    """Delete a project - Soft delete with ownership and task check"""
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    project = get_object_or_404(Projects, id=id)
    project_name = project.name
    
    # Only allow POST requests
    if request.method != 'POST':
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
        return redirect("view_projects")
    
    # 🔒 OWNERSHIP CHECK: Only project creator can delete
    if project.created_by != request.user:
        error_msg = "Only the project creator can delete this project"
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg}, status=403)
        messages.error(request, error_msg)
        return redirect("view_projects")
    
    # 🔒 BLOCK DELETION IF ACTIVE TASKS EXIST
    active_tasks_count = project.task_set.filter(is_deleted=False).count()
    if active_tasks_count > 0:
        error_msg = f"Cannot delete project. Please delete all {active_tasks_count} task(s) first."
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect("view_projects")
    
    # ✅ SOFT DELETE
    from django.utils import timezone
    project.is_deleted = True
    project.deleted_at = timezone.now()
    project.save()
    
    # 📝 LOG TO ACTIVITY LOG
    from users.models import ActivityLog
    ActivityLog.objects.create(
        user=request.user,
        action='deleted',
        entity_type='project',
        entity_id=project.id,
        entity_name=project.name
    )
    
    # Return success response
    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': f'Project "{project_name}" moved to trash successfully!'
        })
    else:
        messages.success(request, f'Project "{project_name}" moved to trash successfully!')
        if can_view_all_projects(request.user):
            return redirect("view_projects")
        return redirect(dashboard_url_for(request.user))
    



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

                # 📝 LOG TO ACTIVITY LOG - PROJECT CREATED (AJAX)
                from users.models import ActivityLog
                ActivityLog.objects.create(
                    user=request.user,
                    action='created',
                    entity_type='project',
                    entity_id=project.id,
                    entity_name=project.name
                )
                
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
                                is_read=False,
                                content_object=project
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

            # 📝 LOG TO ACTIVITY LOG - PROJECT CREATED
            from users.models import ActivityLog
            ActivityLog.objects.create(
                user=request.user,
                action='created',
                entity_type='project',
                entity_id=project.id,
                entity_name=project.name
            )
            
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
                            is_read=False,
                            content_object=project
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




