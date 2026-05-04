from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from users.models import User

from projects.models import Projects
from .serializers import (
    ProjectSerializer,
)

from users.permissions import (
    can_manage_projects,
    can_view_all_projects,
    can_change_projects,
    is_manager_like,
    get_projects_queryset,
)



class ProjectPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ProjectListAPIView(APIView):
    """GET /api/projects/  —  permission-filtered project list with pagination and search"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        search = request.query_params.get('search', '')

        projects = get_projects_queryset(user)

        if search:
            projects = projects.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(assigned_to__username__icontains=search) |
                Q(assigned_to__first_name__icontains=search) |
                Q(assigned_to__last_name__icontains=search)
            ).distinct()

        projects = projects.order_by('-start_date')
        
        paginator = ProjectPagination()
        page = paginator.paginate_queryset(projects, request)
        
        if page is not None:
            serializer = ProjectSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ProjectSerializer(projects, many=True)
        return Response({
            'count': projects.count(),
            'results': serializer.data,
        })
    
    def post(self, request):
        """Create a new project"""
        user = request.user
        
        # Permission check
        if not user.has_perm('projects.add_projects'):
            return Response(
                {'error': 'You do not have permission to create projects'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ProjectSerializer(data=request.data)
        if serializer.is_valid():
            project = serializer.save(created_by=user)
            
            # Initialize assigned_to_ids as empty list
            assigned_to_ids = []
            
            # Handle assigned_to if provided
            if 'assigned_to' in request.data:
                assigned_to_ids = request.data.get('assigned_to', [])
                if assigned_to_ids:
                    project.assigned_to.set(assigned_to_ids)
            
            # Activity log
            from users.models import ActivityLog
            ActivityLog.objects.create(
                user=user,
                action='created',
                entity_type='project',
                entity_id=project.id,
                entity_name=project.name
            )
            
            # Send notifications to assigned users (only if assigned_to_ids has values)
            if assigned_to_ids:  # Now this variable is always defined
                from notifications.models import Notification
                for user_id in assigned_to_ids:
                    assigned_user = User.objects.filter(id=user_id).first()
                    if assigned_user:
                        Notification.objects.create(
                            user=assigned_user,
                            message=f'📁 You have been assigned to project "{project.name}" by {request.user.get_full_name() or request.user.username}.',
                            is_read=False,
                            content_object=project
                        )
            
            return Response(
                ProjectSerializer(project).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(
            {'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )


class ProjectDetailAPIView(APIView):
    """
    GET    /api/projects/<id>/  —  Retrieve project detail
    PATCH  /api/projects/<id>/  —  Update project
    DELETE /api/projects/<id>/  —  Delete project
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            project = Projects.objects.get(pk=pk)
            # Permission check: can view detail if admin, assigned, or has global change permission
            if can_view_all_projects(user) or can_change_projects(user):
                return project
            if project.assigned_to.filter(id=user.id).exists():
                return project
            return None
        except Projects.DoesNotExist:
            return None

    def get(self, request, pk):
        project = self.get_object(pk, request.user)
        if not project:
            return Response({'error': 'Project not found or access denied'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ProjectSerializer(project)
        return Response(serializer.data)

    def patch(self, request, pk):
        project = self.get_object(pk, request.user)
        if not project:
            return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # 🔒 OWNERSHIP CHECK: Only project creator can edit
        if project.created_by != request.user:
            return Response(
                {'error': 'Only the project creator can edit this project'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not can_manage_projects(request.user) and not request.user.is_superuser:
            return Response(
                {'error': 'You do not have permission to edit projects'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 📝 Capture old values (including assigned_to)
        old_data = {
            'name': project.name,
            'description': project.description,
            'status': project.status,
            'start_date': str(project.start_date) if project.start_date else None,
            'end_date': str(project.end_date) if project.end_date else None,
            'assigned_to': [user.email for user in project.assigned_to.all()],
        }
        
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        if serializer.is_valid():
            # Set updated_by before saving
            project.updated_by = request.user
            serializer.save()
            
            # Handle ManyToMany field (assigned_to) separately if needed
            if 'assigned_to' in request.data:
                assigned_to_ids = request.data.get('assigned_to', [])
                if assigned_to_ids:
                    project.assigned_to.set(assigned_to_ids)
                else:
                    project.assigned_to.clear()
            
            # 📝 Capture new values (including assigned_to)
            new_data = {
                'name': project.name,
                'description': project.description,
                'status': project.status,
                'start_date': str(project.start_date) if project.start_date else None,
                'end_date': str(project.end_date) if project.end_date else None,
                'assigned_to': [user.email for user in project.assigned_to.all()],
            }
            
            # 📝 Find what changed
            changes = []
            for field in old_data:
                if old_data[field] != new_data[field]:
                    if field == 'assigned_to':
                        old_users = set(old_data[field])
                        new_users = set(new_data[field])
                        added = new_users - old_users
                        removed = old_users - new_users
                        if added:
                            changes.append(f"• assigned_to: added {', '.join(added)}")
                        if removed:
                            changes.append(f"• assigned_to: removed {', '.join(removed)}")
                    else:
                        changes.append(f"• {field}: '{old_data[field]}' → '{new_data[field]}'")
            
            change_summary = '\n'.join(changes) if changes else 'No visible changes'
            
            # 📝 LOG TO ACTIVITY LOG WITH DETAILS
            from users.models import ActivityLog
            import json
            ActivityLog.objects.create(
                user=request.user,
                action='updated',
                entity_type='project',
                entity_id=project.id,
                entity_name=project.name,
                old_value=json.dumps(old_data, default=str),
                new_value=json.dumps(new_data, default=str)
            )
            
            return Response({
                'success': True, 
                'message': f'Project updated successfully.\n{change_summary}', 
                'project': serializer.data
            })
        
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        project = self.get_object(pk, request.user)
        if not project:
            return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

        # 🔒 OWNERSHIP CHECK
        if project.created_by != request.user:
            return Response(
                {'error': f'Only the project creator can delete this project. Creator: {project.created_by}, You: {request.user}'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 🔒 OWNERSHIP CHECK: Only project creator can delete
        if project.created_by != request.user:
            return Response(
                {'error': 'Only the project creator can delete this project'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 🔒 BLOCK DELETION IF ACTIVE TASKS EXIST
        active_tasks_count = project.task_set.filter(is_deleted=False).count()
        if active_tasks_count > 0:
            return Response(
                {'error': f'Cannot delete project. Please delete all {active_tasks_count} task(s) first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
        
        return Response({'success': True, 'message': 'Project moved to trash successfully'})

