from rest_framework import serializers
from django.contrib.auth import get_user_model
from projects.models import Projects
from users.api.serializers import UserSerializer
User = get_user_model()


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