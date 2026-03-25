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

        # Fix superuser role if empty
        if user.is_superuser and not user.role:
            user.role = 'ADMIN'
            user.save()

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        role = user.role if user.role else 'EMPLOYEE'

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
    """GET /api/projects/  —  role-filtered project list"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role == 'ADMIN' or user.is_superuser:
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
    """GET /api/users/  —  admin-only user list"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'ADMIN' and not request.user.is_superuser:
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )

        users = User.objects.all().order_by('-date_joined')
        serializer = UserSerializer(users, many=True)
        return Response({
            'count': users.count(),
            'results': serializer.data,
        })


class TaskListAPIView(APIView):
    """GET /api/tasks/  —  role-filtered task list"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role == 'ADMIN' or user.is_superuser:
            tasks = Task.objects.all()
        elif user.role == 'TEAM_LEAD':
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
    """GET /api/dashboard/  —  role-based dashboard stats"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role.upper() if user.role else 'EMPLOYEE'

        if role == 'ADMIN' or user.is_superuser:
            return Response({
                'role': 'ADMIN',
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

        elif role == 'TEAM_LEAD':
            my_projects = Projects.objects.filter(assigned_to=user)
            project_ids = my_projects.values_list('id', flat=True)
            my_tasks = Task.objects.filter(project_id__in=project_ids)
            return Response({
                'role': 'TEAM_LEAD',
                'stats': {
                    'total_projects': my_projects.count(),
                    'active_tasks': my_tasks.filter(status='ONGOING').count(),
                    'completed_tasks': my_tasks.filter(status='COMPLETED').count(),
                    'pending_tasks': my_tasks.filter(status='PENDING').count(),
                    'team_members': User.objects.filter(role='EMPLOYEE').count(),
                },
            })

        else:  # EMPLOYEE
            tasks = Task.objects.filter(assigned_to=user)
            projects = Projects.objects.filter(assigned_to=user)
            return Response({
                'role': 'EMPLOYEE',
                'stats': {
                    'tasks_count': tasks.count(),
                    'ongoing_tasks': tasks.filter(status='ONGOING').count(),
                    'completed_tasks': tasks.filter(status='COMPLETED').count(),
                    'pending_tasks': tasks.filter(status='PENDING').count(),
                    'projects_count': projects.count(),
                },
            })
