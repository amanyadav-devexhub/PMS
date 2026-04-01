from django import forms
from django.contrib.auth.models import Permission
from django.contrib.auth.forms import UserCreationForm
from .models import Role, User, UserProfile, Department, Designation
from projects.models import Projects

class UserRegisterForm(UserCreationForm):
    role_obj = forms.ModelChoiceField(
        queryset=Role.objects.none(),
        required=True,
        empty_label="Select a role",
        label="Role"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'role_obj', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role_obj'].queryset = Role.objects.order_by('name')

    def save(self, commit=True):
        user = super().save(commit=False)
        selected_role = self.cleaned_data.get('role_obj')
        user.role_obj = selected_role
        user.role = selected_role.name if selected_role else user.role
        if commit:
            user.save()
        return user

    
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


