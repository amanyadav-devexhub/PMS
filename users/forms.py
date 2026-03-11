from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from projects.models import Projects
from Tasks.models import Task

class UserRegisterForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'password1', 'password2']

    
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