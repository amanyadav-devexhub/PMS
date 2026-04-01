from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from projects.models import Projects
from Tasks.models import Task
from django.contrib.auth.models import Permission
from .models import User, Role, UserProfile

class UserRegisterForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'password1', 'password2']

    # Remove password1 and password2 fields since we're not setting password
    # Or make them optional
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput,
        required=False,  # Make it optional
        help_text='User will set this via activation link'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput,
        required=False,  # Make it optional
        help_text='User will set this via activation link'
    )
    
    def clean_password2(self):
        # Bypass password validation since we're not using it
        return self.cleaned_data.get('password1', '')
    
    def clean(self):
        # Skip password validation for admin creation
        return self.cleaned_data

    
    # Project creation form
class ProjectForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    # ✅ Explicitly set assigned_to as ModelMultipleChoiceField
    assigned_to = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.SelectMultiple(attrs={
            'size': 5,
            'class': 'w-full border rounded px-4 py-2'
        }),
        required=False
    )
    class Meta:
        model = Projects
        fields = ['name', 'description','assigned_to' ,'start_date', 'end_date','status']


class RoleForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related('content_type').none(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Role
        fields = ['name', 'permissions']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['permissions'].queryset = Permission.objects.select_related('content_type').filter(
            content_type__app_label__in=['users', 'projects', 'Tasks', 'notifications', 'tasks']
        ).order_by('content_type__app_label', 'codename')

from django import forms
from .models import UserProfile, Department, Designation

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['employee_id', 'phone', 'department', 'designation', 'date_of_joining']
        widgets = {
            'date_of_joining': forms.DateInput(attrs={'type': 'date', 'class': 'w-full border rounded px-4 py-2'}),
            'employee_id': forms.TextInput(attrs={'class': 'w-full border rounded px-4 py-2'}),
            'phone': forms.TextInput(attrs={'class': 'w-full border rounded px-4 py-2'}),
            'department': forms.Select(attrs={'class': 'w-full border rounded px-4 py-2'}),
            'designation': forms.Select(attrs={'class': 'w-full border rounded px-4 py-2'}),
        }


from django.contrib.contenttypes.models import ContentType

class PermissionForm(forms.ModelForm):
    class Meta:
        model = Permission
        fields = ['name', 'codename', 'content_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full border rounded px-4 py-2'}),
            'codename': forms.TextInput(attrs={'class': 'w-full border rounded px-4 py-2'}),
            'content_type': forms.Select(attrs={'class': 'w-full border rounded px-4 py-2'}),
        }


