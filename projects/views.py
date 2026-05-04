from django.shortcuts import render, get_object_or_404, redirect  # ← Keep only one
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.template.loader import render_to_string

from notifications.models import Notification  
from projects.models import Projects, ProjectResource
from Tasks.models import Task
from .forms import ProjectForm, ProjectResourceForm, ProjectResourceFormSet
from users.models import User
from users.decorators import jwt_or_session_required, permission_required
from users.permissions import (  
    can_view_all_projects,
    can_manage_users,
    is_manager_like,
    can_change_projects,
    dashboard_url_for,
    get_task_queryset,
    get_projects_queryset,  
)



@jwt_or_session_required
@permission_required('projects.view_projects')
def view_projects(request):
    return render(request, "view_projects.html", {
        'can_add_projects': request.user.has_perm('projects.add_projects'),
        'can_delete_projects': request.user.has_perm('projects.delete_projects'),
    })



@jwt_or_session_required
@permission_required('projects.change_projects')
@csrf_exempt
def edit_projects(request, project_id):
    """Render edit form - submission handled by API"""
    
    project = get_object_or_404(Projects, id=project_id)
    
    # 🔒 Ownership check
    if project.created_by != request.user:
        messages.error(request, 'Only the project creator can edit this project')
        return redirect('view_projects')
    
    # Helper function to filter users based on role
    def get_filtered_users(user):
        all_active_users = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True).order_by('first_name', 'username')
        
        if can_manage_users(user):
            return all_active_users
        
        manager_ids = [u.id for u in all_active_users if is_manager_like(u)]
        return all_active_users.exclude(id__in=manager_ids)
    
    # Create form with filtered user queryset
    filtered_users = get_filtered_users(request.user)
    
    class FilteredProjectForm(ProjectForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['assigned_to'].queryset = filtered_users
    
    form = FilteredProjectForm(instance=project)
    
    # Just render the HTML form
    return render(request, "edit_projects.html", {
        "form": form,
        "project": project
    })


@jwt_or_session_required
@permission_required('projects.view_projects')
def view_project_detail(request, project_id):
    """Render project detail page - tasks data loaded via API"""
    
    project = get_object_or_404(Projects, id=project_id, is_deleted=False)
    
    # Permission check
    if not can_view_all_projects(request.user) and request.user not in project.assigned_to.all():
        messages.error(request, "You don't have permission to view this project.")
        return redirect('view_projects')
    
    # Just render the HTML template with basic info
    return render(request, "view_project_detail.html", {
        "project": project,
        "is_manager_like": is_manager_like(request.user),
        "can_add_task": request.user.has_perm('Tasks.add_task'),
    })



@jwt_or_session_required
@csrf_exempt
def add_project_resource(request, project_id):
    """Add resource to project - handles file uploads"""
    
    project = get_object_or_404(Projects, id=project_id)
    
    if request.method == "POST":
        form = ProjectResourceForm(request.POST, request.FILES)
        if form.is_valid():
            resource = form.save(commit=False)
            resource.project = project
            resource.save()
            messages.success(request, f'Resource "{resource.name}" added successfully!')
            return redirect("view_project_detail", project_id=project.id)
    else:
        form = ProjectResourceForm()
    
    return render(request, "add_project_resource.html", {
        "form": form,
        "project": project
    })


    
@jwt_or_session_required
@permission_required('projects.add_projects')
@csrf_exempt
def create_project(request):
    """Render create form - submission can be handled by form or API"""
    
    def get_filtered_users(user):
        all_active_users = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True).order_by('first_name', 'username')
        if can_manage_users(user):
            return all_active_users
        manager_ids = [u.id for u in all_active_users if is_manager_like(u)]
        return all_active_users.exclude(id__in=manager_ids)
    
    filtered_users = get_filtered_users(request.user)
    
    class FilteredProjectForm(ProjectForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['assigned_to'].queryset = filtered_users
    
    # GET request - just render the form
    if request.method == "GET":
        project_form = FilteredProjectForm()
        resource_formset = ProjectResourceFormSet()
        
        return render(request, "create_project.html", {
            "form": project_form,
            "resource_formset": resource_formset
        })
    
    # POST request - handle form submission (for non-AJAX)
    if request.method == "POST":
        project_form = FilteredProjectForm(request.POST)
        resource_formset = ProjectResourceFormSet(request.POST, request.FILES)
        
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Date validation
        if start_date and end_date and start_date >= end_date:
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
            
            # Activity log
            from users.models import ActivityLog
            ActivityLog.objects.create(
                user=request.user,
                action='created',
                entity_type='project',
                entity_id=project.id,
                entity_name=project.name
            )
            
            # Assign users
            assigned_users = []
            if project_form.cleaned_data.get('assigned_to'):
                assigned_users = list(project_form.cleaned_data['assigned_to'])
                project.assigned_to.set(assigned_users)
            
            # Save resources
            for resource_form in resource_formset:
                if resource_form.cleaned_data and not resource_form.cleaned_data.get('DELETE', False):
                    resource = resource_form.save(commit=False)
                    resource.project = project
                    resource.save()
            
            # Send notifications
            if assigned_users:
                for user in assigned_users:
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

            messages.success(request, "Project created successfully!")
            if can_view_all_projects(request.user):
                return redirect("view_projects")
            return redirect(dashboard_url_for(request.user))
        else:
            # Form errors
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



@jwt_or_session_required
@permission_required('projects.view_projects')
@csrf_exempt
def employee_projects(request):

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get('search', '').strip()
        page = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 9)  
        
        projects = get_projects_queryset(request.user)
        
        if search_query:
            projects = projects.filter(
                models.Q(name__icontains=search_query) |
                models.Q(description__icontains=search_query)
            ).distinct()
        
        projects = projects.order_by('-start_date')
        
        total_projects = projects.count()
        ongoing_projects = projects.filter(status='ONGOING').count()
        completed_projects = projects.filter(status='COMPLETED').count()
        
        paginator = Paginator(projects, page_size)
        try:
            projects_page = paginator.page(page)
        except PageNotAnInteger:
            projects_page = paginator.page(1)
        except EmptyPage:
            projects_page = paginator.page(paginator.num_pages)
        
        projects_data = []
        for project in projects_page:
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
    
    return render(request, "employee_projects.html")
