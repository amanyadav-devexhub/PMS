from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model

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

class ProjectListAPIView(APIView):
    """GET /api/projects/  —  permission-filtered project list"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if can_view_all_projects(user):
            projects = Projects.objects.all()
        else:
            projects = Projects.objects.filter(assigned_to=user)

        projects = projects.order_by('-start_date')
        serializer = ProjectSerializer(projects, many=True)
        return Response({
            'count': projects.count(),
            'results': serializer.data,
        })


class UserListAPIView(APIView):
    """GET /api/users/  —  permission-gated user list"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_manage_users(request.user):
            return Response(
                {'error': 'Insufficient permission to view users'},
                status=status.HTTP_403_FORBIDDEN
            )

        users = User.objects.all().order_by('-date_joined')
        serializer = UserSerializer(users, many=True)
        return Response({
            'count': users.count(),
            'results': serializer.data,
        })


class TaskListAPIView(APIView):
    """GET /api/tasks/  —  permission-filtered task list"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if can_view_all_tasks(user):
            tasks = Task.objects.all()
        elif can_add_task(user) or can_manage_projects(user):
            my_project_ids = Projects.objects.filter(
                assigned_to=user
            ).values_list('id', flat=True)
            tasks = Task.objects.filter(project_id__in=my_project_ids)
        else:
            tasks = Task.objects.filter(assigned_to=user)

        tasks = tasks.order_by('-created_at')
        serializer = TaskSerializer(tasks, many=True)
        return Response({
            'count': tasks.count(),
            'results': serializer.data,
        })


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
