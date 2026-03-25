from rest_framework import serializers
from django.contrib.auth import get_user_model
from projects.models import Projects
from Tasks.models import Task

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'is_active', 'full_name', 'date_joined']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ProjectSerializer(serializers.ModelSerializer):
    assigned_to = UserSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Projects
        fields = [
            'id', 'name', 'description', 'assigned_to',
            'start_date', 'end_date', 'created_by', 'status'
        ]


class TaskSerializer(serializers.ModelSerializer):
    assigned_to = UserSerializer(many=True, read_only=True)
    assigned_by = UserSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'name', 'description', 'project', 'project_name',
            'assigned_to', 'assigned_by', 'start_date', 'end_date',
            'status', 'start_time', 'end_time', 'total_time',
            'estimated_time', 'created_at', 'deadline', 'summary'
        ]
