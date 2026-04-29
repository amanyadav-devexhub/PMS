from rest_framework import serializers
from Tasks.models import Task
from users.models import User
from projects.models import Projects
from users.api.serializers import UserSerializer
from django.utils import timezone



class ProjectSerializer(serializers.ModelSerializer):
    assigned_to_details = UserSerializer(source='assigned_to', many=True, read_only=True)
    created_by_details = UserSerializer(source='created_by', read_only=True)

    class Meta:
        model = Projects
        fields = [
            'id', 'name', 'description', 'assigned_to', 'assigned_to_details',
            'start_date', 'end_date', 'created_by', 'created_by_details', 'status'
        ]
        extra_kwargs = {
            'assigned_to': {'required': False},
            'created_by': {'required': False}
        }



class TaskSerializer(serializers.ModelSerializer):
    assigned_to_details = UserSerializer(source='assigned_to', many=True, read_only=True)
    assigned_by_details = UserSerializer(source='assigned_by', many=True, read_only=True)
    observers_details = UserSerializer(source='observers', many=True, read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    time_display = serializers.SerializerMethodField()
    total_paused_duration_seconds = serializers.SerializerMethodField()
    truncated_name = serializers.SerializerMethodField()
    is_paused = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'name', 'description', 'project', 'project_name',
            'assigned_to', 'assigned_to_details', 
            'assigned_by', 'assigned_by_details',
            'observers', 'observers_details',
            'start_date', 'end_date', 'status', 'status_display',
            'start_time', 'end_time', 'total_time', 'estimated_time', 
            'created_at', 'deadline', 'summary', 'time_display', 'total_paused_duration_seconds',
            'truncated_name','is_paused'
        ]
        extra_kwargs = {
            'assigned_to': {'required': False},
            'assigned_by': {'required': False},
            'observers': {'required': False},
        }

    def get_time_display(self, obj):
    
    # For completed tasks
        if obj.status == 'COMPLETED' and obj.total_time:
            total_seconds = int(obj.total_time.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # For ongoing tasks (including paused)
        if obj.status == 'ONGOING' and obj.start_time:
            now = timezone.now()
            elapsed = now - obj.start_time
            
            if obj.total_paused_duration:
                elapsed = elapsed - obj.total_paused_duration
            
            # If currently paused, subtract current pause duration
            if obj.paused_time:
                current_pause = now - obj.paused_time
                elapsed = elapsed - current_pause
            
            total_seconds = int(elapsed.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        return "00:00:00"

    def get_total_paused_duration_seconds(self, obj):
        if obj.total_paused_duration:
            return int(obj.total_paused_duration.total_seconds())
        return 0

    def get_truncated_name(self, obj):
        if not obj.name:
            return ""
        words = obj.name.split()
        if len(words) > 20:
            return " ".join(words[:20]) + "..."
        return obj.name

    def get_is_paused(self, obj):  
        return obj.paused_time is not None