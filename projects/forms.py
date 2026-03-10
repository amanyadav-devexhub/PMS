from django import forms
from .models import ProjectResource

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