from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from projects.models import Projects
from Tasks.models import Task
from django.contrib.auth.models import Permission
from .models import User, Role, UserProfile

class UserRegisterForm(UserCreationForm):
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=False)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = User
        fields = ['username', 'email','first_name', 'last_name', 'role', 'password1', 'password2']

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput,
        required=False,  
        help_text='User will set this via activation link'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput,
        required=False,  
        help_text='User will set this via activation link'
    )
    
    def clean_password2(self):
        return self.cleaned_data.get('password1', '')
    
    def clean(self):
        return self.cleaned_data

class ProjectForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
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

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if not employee_id or not employee_id.strip():
            raise forms.ValidationError("Employee ID is required.")
        
        if self.instance and self.instance.pk:
            if UserProfile.objects.exclude(pk=self.instance.pk).filter(employee_id=employee_id.strip()).exists():
                raise forms.ValidationError("Employee ID already exists.")
        else:
            if UserProfile.objects.filter(employee_id=employee_id.strip()).exists():
                raise forms.ValidationError("Employee ID already exists.")
        
        return employee_id.strip()

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


