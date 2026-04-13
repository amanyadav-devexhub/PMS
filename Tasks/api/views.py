import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q

from Tasks.models import Task
from .serializers import TaskSerializer
from users.permissions import (
    can_add_task, can_manage_projects, can_change_task,
    can_view_all_tasks, can_view_task, get_task_queryset
)

class TaskPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class TaskListAPIView(APIView):
    """GET /api/tasks/  —  filtered task list with pagination and project support"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        project_id = request.query_params.get('project_id')
        task_id = request.query_params.get('task_id')
        assigned_to = request.query_params.get('assigned_to')
        search = request.query_params.get('search', '')

        # Use centralized permission-filtered queryset
        tasks = get_task_queryset(user)
        
        if project_id:
            tasks = tasks.filter(project_id=project_id)
        
        if task_id:
            tasks = tasks.filter(id=task_id)
            
        if assigned_to:
            tasks = tasks.filter(assigned_to__id=assigned_to)

        if search:
            tasks = tasks.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(assigned_to__username__icontains=search)
            ).distinct()

        tasks = tasks.order_by('-created_at')
        
        paginator = TaskPagination()
        page = paginator.paginate_queryset(tasks, request)
        
        if page is not None:
            serializer = TaskSerializer(page, many=True)
            response = paginator.get_paginated_response(serializer.data)
            
            # Add some stats if project_id is provided
            if project_id:
                try:
                    project_tasks = Task.objects.filter(project_id=project_id)
                    response.data.update({
                        'total_tasks': project_tasks.count(),
                        'pending_tasks': project_tasks.filter(status='PENDING').count(),
                        'ongoing_tasks': project_tasks.filter(status='ONGOING').count(),
                        'completed_tasks': project_tasks.filter(status='COMPLETED').count(),
                    })
                except (ValueError, TypeError):
                    pass
            return response

        serializer = TaskSerializer(tasks, many=True)
        return Response({
            'count': tasks.count(),
            'results': serializer.data,
        })


class TaskDetailAPIView(APIView):
    """
    GET    /api/tasks/<id>/  —  Retrieve task detail
    PATCH  /api/tasks/<id>/  —  Update task
    DELETE /api/tasks/<id>/  —  Delete task
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            task = Task.objects.get(pk=pk)
            # Permission check: admin, manager of project, assigned to task, observer, or global change perm
            if can_view_all_tasks(user) or can_change_task(user):
                return task
            if task.assigned_to.filter(id=user.id).exists() or task.observers.filter(id=user.id).exists():
                return task
            if task.project and task.project.assigned_to.filter(id=user.id).exists() and (can_add_task(user) or can_manage_projects(user)):
                return task
            return None
        except Task.DoesNotExist:
            return None

    def get(self, request, pk):
        task = self.get_object(pk, request.user)
        if not task:
            return Response({'error': 'Task not found or access denied'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TaskSerializer(task)
        return Response(serializer.data)

    def patch(self, request, pk):
        task = self.get_object(pk, request.user)
        if not task:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # 🔒 OWNERSHIP CHECK: Task owner OR project creator can edit
        is_task_owner = task.assigned_by.filter(id=request.user.id).exists()
        is_project_creator = task.project.created_by == request.user
        is_admin_override = request.user.is_superuser
        
        if not (is_task_owner or is_project_creator or is_admin_override):
            return Response(
                {'error': 'Only task owner or project creator can edit this task'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Optional: Also check if user has edit permission (for safety)
        if not (can_change_task(request.user) or can_manage_projects(request.user)) and not is_admin_override:
            return Response(
                {'error': 'You do not have permission to edit tasks'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # ========== ✅ ADD THIS SECTION - Capture old values safely ==========
        old_data = {
            'name': task.name,
            'description': task.description,
            'status': task.status,
            'start_date': str(task.start_date) if task.start_date else None,
            'end_date': str(task.end_date) if task.end_date else None,
            'deadline': str(task.deadline) if task.deadline else None,
            'estimated_time': task.estimated_time,
        }
        
        # Capture ManyToMany for logging
        old_assigned_to = [user.email for user in task.assigned_to.all()]
        old_assigned_by = [user.email for user in task.assigned_by.all()]
        old_observers = [user.email for user in task.observers.all()]
        # ========== END OF ADDED SECTION ==========

        serializer = TaskSerializer(task, data=request.data, partial=True)
        if serializer.is_valid():
            updated_task = serializer.save()
            
            # ========== ✅ ADD THIS SECTION - Handle ManyToMany fields safely ==========
            # Only update if the field exists in the request
            if 'assigned_to' in request.data:
                assigned_to_ids = request.data.get('assigned_to', [])
                if assigned_to_ids:
                    updated_task.assigned_to.set(assigned_to_ids)
                else:
                    updated_task.assigned_to.clear()
            
            if 'assigned_by' in request.data:
                assigned_by_ids = request.data.get('assigned_by', [])
                if assigned_by_ids:
                    updated_task.assigned_by.set(assigned_by_ids)
                else:
                    updated_task.assigned_by.clear()
            
            if 'observers' in request.data:
                observer_ids = request.data.get('observers', [])
                if observer_ids:
                    updated_task.observers.set(observer_ids)
                else:
                    updated_task.observers.clear()
            # ========== END OF ADDED SECTION ==========
            
            # ========== ✅ ADD THIS SECTION - Capture new values for logging ==========
            new_data = {
                'name': updated_task.name,
                'description': updated_task.description,
                'status': updated_task.status,
                'start_date': str(updated_task.start_date) if updated_task.start_date else None,
                'end_date': str(updated_task.end_date) if updated_task.end_date else None,
                'deadline': str(updated_task.deadline) if updated_task.deadline else None,
                'estimated_time': updated_task.estimated_time,
            }
            
            new_assigned_to = [user.email for user in updated_task.assigned_to.all()]
            new_assigned_by = [user.email for user in updated_task.assigned_by.all()]
            new_observers = [user.email for user in updated_task.observers.all()]
            
            # Find changes
            changes = []
            for field in old_data:
                if old_data[field] != new_data[field]:
                    changes.append(f"{field}: '{old_data[field]}' → '{new_data[field]}'")
            
            if set(old_assigned_to) != set(new_assigned_to):
                changes.append(f"assigned_to: {old_assigned_to} → {new_assigned_to}")
            if set(old_assigned_by) != set(new_assigned_by):
                changes.append(f"assigned_by: {old_assigned_by} → {new_assigned_by}")
            if set(old_observers) != set(new_observers):
                changes.append(f"observers: {old_observers} → {new_observers}")
            
            change_summary = ', '.join(changes) if changes else 'No visible changes'
            # ========== END OF ADDED SECTION ==========
            
            # 📝 LOG TO ACTIVITY LOG
            from users.models import ActivityLog
            ActivityLog.objects.create(
                user=request.user,
                action='updated',
                entity_type='task',
                entity_id=updated_task.id,
                entity_name=updated_task.name
            )
            
            # ========== ✅ MODIFY THIS RETURN - Add change summary ==========
            return Response({
                'success': True, 
                'message': f'Task updated successfully. Changes: {change_summary}', 
                'task': serializer.data
            })
            # ========== END OF MODIFIED SECTION ==========
        
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        task = self.get_object(pk, request.user)
        if not task:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # 🔒 OWNERSHIP CHECK: Task owner OR project creator can delete
        is_task_owner = task.assigned_by.filter(id=request.user.id).exists()
        is_project_creator = task.project.created_by == request.user
        
        if not (is_task_owner or is_project_creator):
            return Response(
                {'error': 'Only task owner or project creator can delete this task'},
                status=status.HTTP_403_FORBIDDEN
            )
        
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
        
        return Response({'success': True, 'message': 'Task moved to trash successfully'})