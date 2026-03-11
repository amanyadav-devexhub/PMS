
from django import forms
from .models import Task  # Import from same app
from projects.models import Projects  # Import from other app

class TaskForm(forms.ModelForm):

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model = Task
        fields = ['name', 'description','project' ,'assigned_to', 'status','start_date','end_date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show employees for assignment
        self.fields['assigned_to'].queryset = User.objects.filter(role='EMPLOYEE')
         # Show all projects in dropdown
        self.fields['project'].queryset = Projects.objects.all()