from django import forms
from .models import ProjectResource
from django.contrib.auth.models import User
from users.models import User, Role, UserProfile

class ProjectResourceForm(forms.ModelForm):
    class Meta:
        model = ProjectResource
        fields = ['resource_type', 'title', 'text_content', 'file', 'link']

from django.forms import inlineformset_factory

from .models import Projects

ProjectResourceFormSet = inlineformset_factory(
    Projects, ProjectResource, form=ProjectResourceForm,
    extra=1, can_delete=True
)

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