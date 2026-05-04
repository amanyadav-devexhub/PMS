from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg
from users.models import User, UserProfile
from django.utils import timezone
from users.models import Department,Designation
from datetime import timedelta
from .serializers import (
    UserSerializer,
    LoginSerializer,
    
)
from projects.models import Projects
from Tasks.models import Task
from users.permissions import (
    can_add_task,
    can_manage_projects,
    can_manage_users,
    can_view_task,
    can_view_user,
    is_manager_like,
    get_task_queryset,
    get_projects_queryset,
    can_manage_users,
    is_manager_like,
    can_view_task,
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

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'Email does not exist'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        if not user_obj.is_active:
            return Response(
                {'error': 'Your account is inactive. Please contact the administrator.'},
                status=status.HTTP_403_FORBIDDEN
            )

        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response(
                {'error': 'Incorrect password'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if user.role_obj and user.role != user.role_obj.name:
            user.role = user.role_obj.name
            user.save(update_fields=['role'])

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




class UserListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search_query = request.query_params.get('search', '').strip()
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        users = User.objects.all().order_by('-date_joined')
        
        if search_query:
            users = users.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(role__icontains=search_query)
            )
        
        from django.core.paginator import Paginator
        paginator = Paginator(users, page_size)
        users_page = paginator.get_page(page)
        
        # ✅ Build custom response with role_class
        users_data = []
        for user in users_page:
            # Determine role_class based on permissions
            if can_manage_users(user):
                role_class = 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
            elif is_manager_like(user):
                role_class = 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
            elif can_view_task(user):
                role_class = 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
            else:
                role_class = 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400'
            
            role_label = user.role_obj.name if user.role_obj else (user.role or 'UNASSIGNED')
            
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': role_label,
                'role_display': role_label,
                'role_class': role_class,  
                'is_active': user.is_active,
                'full_name': user.get_full_name() or user.username,
                'view_url': f"/user/{user.id}/",
            })
        
        return Response({
            'success': True,
            'users': users_data,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': users_page.number,
            'has_previous': users_page.has_previous(),
            'has_next': users_page.has_next(),
            'previous_page_number': users_page.previous_page_number() if users_page.has_previous() else None,
            'next_page_number': users_page.next_page_number() if users_page.has_next() else None,
            'page_size': page_size,
            'search_query': search_query
        })
    


class UserDetailAPIView(APIView):
    """GET /api/users/<id>/  —  Get user details with profile and analytics"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        
        if request.user.id != user_id and not request.user.is_superuser and not request.user.has_perm('users.view_user'):
            return Response({
                'success': False,
                'access_denied': True,
                'message': 'Access denied. You can only view your own profile.'
            }, status=403)
        
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'employee_id': f"EMP-{user.id:04d}"}
        )
        
        projects_assigned = Projects.objects.filter(assigned_to=user).count()
        tasks_assigned = Task.objects.filter(assigned_to=user).count()
        completed_tasks = Task.objects.filter(assigned_to=user, status="COMPLETED").count()
        
        performance = 0
        if tasks_assigned > 0:
            performance = int((completed_tasks / tasks_assigned) * 100)
        
        return Response({
            "success": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "full_name": user.get_full_name() or user.username,
                "date_joined": user.date_joined.strftime('%Y-%m-%d') if user.date_joined else None,
                "profile_image": profile.profile_image.url if profile.profile_image else None
            },
            "profile": {
                "profile_image": profile.profile_image.url if profile.profile_image else None,
                "employee_id": profile.employee_id or "—",
                "phone": profile.phone or "—",
                "department": profile.department.name if profile.department else "—",
                "designation": profile.designation.name if profile.designation else "—",
                "date_of_joining": profile.date_of_joining.strftime('%Y-%m-%d') if profile.date_of_joining else "—",
                "ctc": profile.ctc or "—",
                "salary_in_hand": profile.salary_in_hand or "—",
                "bank_name": profile.bank_name or "—",
                "account_no": profile.account_no or "—",
                "ifsc": profile.ifsc or "—",
                "aadhar_no": profile.aadhar_no or "—",
                "pan_no": profile.pan_no or "—",
                "emergency_contact": profile.emergency_contact or "—",
                "address": profile.address or "—"
            },
            "analytics": {
                "projects_assigned": projects_assigned,
                "tasks_assigned": tasks_assigned,
                "completed_tasks": completed_tasks,
                "performance": performance
            }
        })
    

## UserAnalyticsAPIView
class UserAnalyticsAPIView(APIView):
    """GET /api/analytics/  —  User performance analytics"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        selected_user_id = request.query_params.get('user_id')
        get_top_performers = request.query_params.get('get_top_performers') == 'true'
        
        
        def _active_users_queryset():
            return User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True)
        
        def _contributor_user_ids():
            return [u.id for u in _active_users_queryset() if not is_manager_like(u)]
        
        def _contributor_users_queryset():
            contributor_ids = _contributor_user_ids()
            return User.objects.filter(id__in=contributor_ids)
        
        def format_duration(duration):
            if not duration:
                return "00:00:00"
            total_seconds = int(duration.total_seconds())
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            s = total_seconds % 60
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        if not (user.has_perm('Tasks.view_task') or user.has_perm('users.view_user')):
            return Response({
                'success': False, 
                'error': 'You do not have permission to view analytics'
            }, status=status.HTTP_403_FORBIDDEN)

        scoped_manager_mode = can_add_task(user) and not can_manage_users(user)
        full_scope_mode = can_manage_users(user)
        
        
        if scoped_manager_mode:
            my_projects = Projects.objects.filter(assigned_to=user)
            my_project_ids = my_projects.values_list('id', flat=True)
            contributor_ids = set(_contributor_user_ids())
            
            tasks_in_my_projects = Task.objects.filter(project_id__in=my_project_ids)
            task_assignee_ids = set(tasks_in_my_projects.values_list('assigned_to', flat=True).distinct())
            project_member_ids = set(User.objects.filter(projects__in=my_projects).values_list('id', flat=True).distinct())
            all_contributor_ids = (task_assignee_ids | project_member_ids) & contributor_ids
            users = User.objects.filter(id__in=all_contributor_ids).order_by('username')
            users = users | User.objects.filter(id=user.id)
        elif full_scope_mode:
            users = User.objects.all().order_by('username')
        elif can_view_user(user) and not can_add_task(user) and not can_manage_users(user):
            users = User.objects.filter(
                is_active=True
            ).exclude(is_staff=True).exclude(is_superuser=True).exclude(role='ADMIN').order_by('username')
        else:
            users = User.objects.filter(id=user.id)
        
      
        if get_top_performers:
            if scoped_manager_mode:
                my_projects = Projects.objects.filter(assigned_to=user)
                my_project_ids = my_projects.values_list('id', flat=True)
                contributor_ids = set(_contributor_user_ids())
                
                tasks_in_my_projects = Task.objects.filter(project_id__in=my_project_ids)
                task_assignee_ids = set(tasks_in_my_projects.values_list('assigned_to', flat=True).distinct())
                project_member_ids = set(User.objects.filter(projects__in=my_projects).values_list('id', flat=True).distinct())
                visible_user_ids = (task_assignee_ids | project_member_ids) & contributor_ids
                all_users = User.objects.filter(id__in=visible_user_ids)
            elif full_scope_mode:
                all_users = User.objects.filter(is_active=True)
            else:
                all_users = User.objects.filter(id=user.id)
            
            top_performers = []
            for u in all_users:
                if scoped_manager_mode:
                    tasks = Task.objects.filter(assigned_to=u, project_id__in=my_project_ids)
                else:
                    tasks = Task.objects.filter(assigned_to=u)
                
                total_tasks = tasks.count()
                completed_tasks = tasks.filter(status='COMPLETED').count()
                
                if total_tasks > 0:
                    performance_score = int((completed_tasks / total_tasks) * 100)
                else:
                    performance_score = 0
                
                if total_tasks > 0:
                    top_performers.append({
                        'id': u.id,
                        'username': u.username,
                        'email': u.email,
                        'role': u.role,
                        'role_display': u.role,
                        'total_tasks': total_tasks,
                        'completed_tasks': completed_tasks,
                        'performance_score': performance_score
                    })
            
            top_performers.sort(key=lambda x: x['performance_score'], reverse=True)
            
            return Response({
                'success': True,
                'top_performers': top_performers
            })
        
    
        selected_user = None
        if selected_user_id:
            selected_user = get_object_or_404(User, id=selected_user_id)
            
            if scoped_manager_mode:
                visible_ids = set(users.values_list('id', flat=True))
                if selected_user.id not in visible_ids:
                    return Response({
                        'success': False,
                        'error': 'You do not have permission to view this user\'s analytics'
                    }, status=status.HTTP_403_FORBIDDEN)
            
            if scoped_manager_mode:
                my_projects = Projects.objects.filter(assigned_to=user)
                my_project_ids = my_projects.values_list('id', flat=True)
                tasks = Task.objects.filter(assigned_to=selected_user, project_id__in=my_project_ids)
                projects = Projects.objects.filter(assigned_to=selected_user, id__in=my_project_ids)
            elif full_scope_mode:
                tasks = Task.objects.filter(assigned_to=selected_user)
                projects = Projects.objects.filter(assigned_to=selected_user)
            else:
                if selected_user.id != user.id:
                    return Response({
                        'success': False,
                        'error': 'You do not have permission to view this user\'s analytics'
                    }, status=status.HTTP_403_FORBIDDEN)
                tasks = Task.objects.filter(assigned_to=user)
                projects = Projects.objects.filter(assigned_to=user)
        else:
            if scoped_manager_mode:
                my_projects = Projects.objects.filter(assigned_to=user)
                my_project_ids = my_projects.values_list('id', flat=True)
                tasks = Task.objects.filter(project_id__in=my_project_ids)
                projects = Projects.objects.filter(id__in=my_project_ids)
            elif full_scope_mode:
                tasks = Task.objects.all()
                projects = Projects.objects.all()
            else:
                tasks = Task.objects.filter(assigned_to=user)
                projects = Projects.objects.filter(assigned_to=user)
        
     
        total_tasks = tasks.count()
        completed = tasks.filter(status='COMPLETED').count()
        ongoing = tasks.filter(status='ONGOING').count()
        pending = tasks.filter(status='PENDING').count()
        overdue = tasks.filter(deadline__lt=timezone.now()).exclude(status='COMPLETED').count()
        performance = int((completed / total_tasks) * 100) if total_tasks > 0 else 0
        stroke_offset = 283 - (performance * 2.83)
        last_7_days = timezone.now() - timedelta(days=7)
        recent_completed = tasks.filter(status='COMPLETED', end_time__gte=last_7_days).count()
        avg_time = tasks.filter(total_time__isnull=False).aggregate(avg=Avg('total_time'))['avg']
        
  
        completed_tasks_with_time = tasks.filter(status='COMPLETED', total_time__isnull=False, estimated_time__gt=0)
        avg_efficiency = 0
        if completed_tasks_with_time.exists():
            total_eff = 0
            valid_count = 0
            for t in completed_tasks_with_time:
                actual_s = t.total_time.total_seconds()
                if actual_s > 0:
                    eff = (t.estimated_time / actual_s) * 100
                    total_eff += min(eff, 100)
                    valid_count += 1
            if valid_count > 0:
                avg_efficiency = int(total_eff / valid_count)
     
        recent_tasks = tasks.select_related('project').order_by('-created_at')[:8]
        recent_tasks_details = []
        for t in recent_tasks:
            recent_tasks_details.append({
                'id': t.id,
                'name': t.name,
                'project': t.project.name if t.project else "N/A",
                'status': t.status,
                'status_display': t.get_status_display(),
                'time': format_duration(t.total_time),
                'deadline': t.deadline.strftime('%Y-%m-%d %H:%M') if t.deadline else None,
            })
        
        avg_time_formatted = format_duration(avg_time)
        projects_count = projects.count()
        remaining = total_tasks - completed
        
        cards = [
            {"label": "Total", "value": total_tasks, "color": "gray"},
            {"label": "Completed", "value": completed, "color": "green"},
            {"label": "Ongoing", "value": ongoing, "color": "blue"},
            {"label": "Pending", "value": pending, "color": "yellow"},
            {"label": "Overdue", "value": overdue, "color": "red"},
            {"label": "Projects", "value": projects_count, "color": "gray"},
        ]
        
        analytics = {
            'total': total_tasks,
            'completed': completed,
            'ongoing': ongoing,
            'pending': pending,
            'overdue': overdue,
            'projects': projects_count,
            'performance': performance,
            'efficiency': avg_efficiency,
            'stroke_offset': stroke_offset,
            'recent_completed': recent_completed,
            'avg_time': avg_time_formatted,
            'remaining': remaining,
            'cards': cards,
            'recent_tasks': recent_tasks_details,
        }
        
        users_list = []
        for u in users:
            users_list.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'role': u.role,
                'full_name': u.get_full_name() or u.username
            })
        
        selected_user_name = None
        if selected_user:
            selected_user_name = selected_user.username
        elif not selected_user and not full_scope_mode:
            selected_user_name = 'My Performance'
        else:
            selected_user_name = 'All Users'
        
        return Response({
            'success': True,
            'analytics': analytics,
            'selected_user_display': selected_user_name,
            'selected_user_id': selected_user.id if selected_user else None,
            'users': users_list
        })

# ============================================================================
# DASHBOARD ENDPOINT
# ============================================================================

class DashboardAPIView(APIView):
    """GET /api/dashboard/  —  capability-based dashboard stats"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role_obj.name if user.role_obj else (user.role or 'USER')

        if can_manage_users(user):
           
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 5))
            
            users_qs = User.objects.all().order_by('-date_joined')
            
            from django.core.paginator import Paginator
            paginator = Paginator(users_qs, page_size)
            users_page = paginator.get_page(page)
            
            users_data = []
            for u in users_page:
                role_label = u.role_obj.name if u.role_obj else (u.role or 'UNASSIGNED')
                if can_manage_users(u): 
                    role_tier = 'owner'
                elif is_manager_like(u): 
                    role_tier = 'manager'
                elif can_view_task(u): 
                    role_tier = 'contributor'
                else: 
                    role_tier = 'custom'

                profile_image = None
                if hasattr(u, 'profile') and u.profile.profile_image:
                    profile_image = u.profile.profile_image.url
                
                users_data.append({
                    'id': u.id,
                    'username': u.username,
                    'email': u.email,
                    'role': role_label,
                    'role_tier': role_tier,
                    'is_active': u.is_active,
                    'profile_image': profile_image,
                })
            
            return Response({
                'role': role,
                'dashboard_variant': 'owner',
                'stats': {
                    'total_users': User.objects.count(),
                    'active_users': User.objects.filter(is_active=True).count(),
                    'inactive_users': User.objects.filter(is_active=False).count(),
                    'total_projects': Projects.objects.count(),
                    'ongoing_projects': Projects.objects.filter(status='ONGOING').count(),
                    'completed_projects': Projects.objects.filter(status='COMPLETED').count(),
                    'total_tasks': Task.objects.count(),
                    'ongoing_tasks': Task.objects.filter(status='ONGOING').count(),
                    'completed_tasks': Task.objects.filter(status='COMPLETED').count(),
                    'pending_tasks': Task.objects.filter(status='PENDING').count(),
                },
                'users': users_data,
                'pagination': {
                    'total': paginator.count,
                    'total_pages': paginator.num_pages,
                    'current_page': users_page.number,
                    'has_previous': users_page.has_previous(),
                    'has_next': users_page.has_next(),
                    'previous_page_number': users_page.previous_page_number() if users_page.has_previous() else None,
                    'next_page_number': users_page.next_page_number() if users_page.has_next() else None,
                    'page_size': page_size,
                }
            })

        if can_add_task(user) or can_manage_projects(user):
            my_projects = get_projects_queryset(user)
            my_tasks = get_task_queryset(user)
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
            tasks = get_task_queryset(user)
            projects = get_projects_queryset(user)
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
    

## Departmet
class DepartmentListAPIView(APIView):
    """GET /api/departments/  —  List all departments"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        departments = Department.objects.all().order_by('name')
        departments_data = [{"id": dept.id, "name": dept.name} for dept in departments]
        return Response({
            'success': True,
            'departments': departments_data,
            'total': departments.count()
        })
    


## Designation
class DesignationListAPIView(APIView):
    """GET /api/designations/  —  List all designations"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        designations = Designation.objects.all().order_by('name')
        designations_data = [{"id": desig.id, "name": desig.name} for desig in designations]
        return Response({
            'success': True,
            'designations': designations_data,
            'total': designations.count()
        })