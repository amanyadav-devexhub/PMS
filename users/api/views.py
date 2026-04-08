from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

from .serializers import (
    UserSerializer,
    LoginSerializer,
    ProjectSerializer,
    TaskSerializer,
)
from projects.models import Projects
from Tasks.models import Task
from users.permissions import (
    can_add_task,
    can_manage_projects,
    can_manage_users,
    can_view_all_projects,
    can_view_all_tasks,
    can_view_task,
    can_change_projects,
    can_change_task,
    can_manage_all_tasks,
    is_manager_like,
)

User = get_user_model()


# ──────────────────────────────────────────────
#  AUTH ENDPOINTS
# ──────────────────────────────────────────────

class LoginAPIView(APIView):
    """POST /api/auth/login/  —  returns JWT access + refresh tokens"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # Check if user exists
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'Email does not exist'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Check active status
        if not user_obj.is_active:
            return Response(
                {'error': 'Your account is inactive. Please contact the administrator.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Authenticate credentials
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response(
                {'error': 'Incorrect password'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Keep legacy role text synced when a Role object exists.
        if user.role_obj and user.role != user.role_obj.name:
            user.role = user.role_obj.name
            user.save(update_fields=['role'])

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        role = user.role_obj.name if user.role_obj else (user.role or 'USER')

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'role': role,
            'user': UserSerializer(user).data,
        })


class RefreshAPIView(APIView):
    """POST /api/auth/refresh/  —  rotate refresh token"""
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            return Response({
                'access': str(token.access_token),
                'refresh': str(token),
            })
        except Exception:
            return Response(
                {'error': 'Invalid or expired refresh token'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutAPIView(APIView):
    """POST /api/auth/logout/  —  blacklist refresh token"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Successfully logged out'})
        except Exception:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )


class MeAPIView(APIView):
    """GET /api/auth/me/  —  current user profile"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


# ──────────────────────────────────────────────
#  RESOURCE ENDPOINTS
# ──────────────────────────────────────────────

class ProjectPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class TaskPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100



class ProjectListAPIView(APIView):
    """GET /api/projects/  —  permission-filtered project list with pagination and search"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        search = request.query_params.get('search', '')

        if can_view_all_projects(user):
            projects = Projects.objects.all()
        else:
            projects = Projects.objects.filter(assigned_to=user)

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
        
        if not can_manage_projects(request.user):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        # Handle ManyToMany assigned_to manually if needed, 
        # but let's see if ProjectSerializer can be updated to support write.
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'success': True, 'message': 'Project updated', 'project': serializer.data})
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        project = self.get_object(pk, request.user)
        if not project:
            return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if not can_manage_projects(request.user):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        project.delete()
        return Response({'success': True, 'message': 'Project deleted successfully'})



class UserListAPIView(APIView):
    """GET /api/users/  —  permission-gated user list"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # We allow any authenticated user to see the user list for selection 
        # (e.g., when assigning tasks or adding observers).
        # We can still filter for is_active=True for security.
        users = User.objects.filter(is_active=True).order_by('-date_joined')
        serializer = UserSerializer(users, many=True)
        return Response({
            'count': users.count(),
            'results': serializer.data,
        })


class TaskListAPIView(APIView):
    """GET /api/tasks/  —  filtered task list with pagination and project support"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        project_id = request.query_params.get('project_id')
        task_id = request.query_params.get('task_id')
        assigned_to = request.query_params.get('assigned_to')
        search = request.query_params.get('search', '')

        if can_view_all_tasks(user) or can_change_task(user):
            tasks = Task.objects.all()
        elif can_manage_all_tasks(user):
            # Managers/Admins can see tasks in projects they created/assigned, 
            # or tasks they are explicitly assigned to or observing
            my_project_ids = Projects.objects.filter(
                Q(assigned_to=user) | Q(created_by=user)
            ).values_list('id', flat=True)
            tasks = Task.objects.filter(
                Q(project_id__in=my_project_ids) | 
                Q(assigned_to=user) | 
                Q(observers=user)
            ).distinct()
        else:
            # Regular employees see tasks assigned to them or tasks they observe
            tasks = Task.objects.filter(
                Q(assigned_to=user) | 
                Q(observers=user)
            ).distinct()

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
        
        # Managers can update anything, assignees can update status/time (usually)
        # But for simplicity, let's use the can_add_task / can_manage_projects logic
        if not (can_add_task(request.user) or can_manage_projects(request.user)) and not task.assigned_to.filter(id=request.user.id).exists():
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        serializer = TaskSerializer(task, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'success': True, 'message': 'Task updated', 'task': serializer.data})
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        task = self.get_object(pk, request.user)
        if not task:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if not (can_add_task(request.user) or can_manage_projects(request.user)):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        task.delete()
        return Response({'success': True, 'message': 'Task deleted successfully'})


class DashboardAPIView(APIView):
    """GET /api/dashboard/  —  capability-based dashboard stats"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role_obj.name if user.role_obj else (user.role or 'USER')

        if can_manage_users(user):
            return Response({
                'role': role,
                'dashboard_variant': 'owner',
                'stats': {
                    'total_users': User.objects.count(),
                    'active_users': User.objects.filter(is_active=True).count(),
                    'total_projects': Projects.objects.count(),
                    'ongoing_projects': Projects.objects.filter(status='ONGOING').count(),
                    'completed_projects': Projects.objects.filter(status='COMPLETED').count(),
                    'total_tasks': Task.objects.count(),
                    'ongoing_tasks': Task.objects.filter(status='ONGOING').count(),
                    'completed_tasks': Task.objects.filter(status='COMPLETED').count(),
                    'pending_tasks': Task.objects.filter(status='PENDING').count(),
                },
            })

        if can_add_task(user) or can_manage_projects(user):
            my_projects = Projects.objects.filter(assigned_to=user)
            project_ids = my_projects.values_list('id', flat=True)
            my_tasks = Task.objects.filter(project_id__in=project_ids)
            active_users = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True)
            team_members_total = sum(1 for member in active_users if not is_manager_like(member))

            return Response({
                'role': role,
                'dashboard_variant': 'manager',
                'stats': {
                    'total_projects': my_projects.count(),
                    'active_tasks': my_tasks.filter(status='ONGOING').count(),
                    'completed_tasks': my_tasks.filter(status='COMPLETED').count(),
                    'pending_tasks': my_tasks.filter(status='PENDING').count(),
                    'team_members': team_members_total,
                },
            })

        if can_view_task(user):
            tasks = Task.objects.filter(assigned_to=user)
            projects = Projects.objects.filter(assigned_to=user)
            return Response({
                'role': role,
                'dashboard_variant': 'contributor',
                'stats': {
                    'tasks_count': tasks.count(),
                    'ongoing_tasks': tasks.filter(status='ONGOING').count(),
                    'completed_tasks': tasks.filter(status='COMPLETED').count(),
                    'pending_tasks': tasks.filter(status='PENDING').count(),
                    'projects_count': projects.count(),
                },
            })

        return Response({
            'role': role,
            'dashboard_variant': 'custom',
            'stats': {
                'tasks_count': 0,
                'ongoing_tasks': 0,
                'completed_tasks': 0,
                'pending_tasks': 0,
                'projects_count': 0,
            },
        })
