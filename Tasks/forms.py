
from django import forms
from .models import Task  # Import from same app
from projects.models import Projects  # Import from other app
from django.utils import timezone
import datetime

class TaskForm(forms.ModelForm):
    # Date fields with widgets
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    # New field for deadline with time
    deadline = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        help_text="Format: YYYY-MM-DD HH:MM"
    )

    class Meta:
        model = Task
        fields = [
            'name', 
            'description',
            'project',
            'assigned_to',
            'assigned_by',  # New field
            'status',
            'start_date',
            'end_date',
            'deadline',     # New field
            'observers',
            'summary',
            'estimated_time',     # New field
        ]

        widgets = {
            'estimated_time': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Time in seconds'})
        },

        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'summary': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Enter task completion summary...'}),
        }

        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'observers': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5}),
        }
        labels = {
            'assigned_by': 'Task Owner',
            'observers': 'Task Observers',
        }
        help_texts = {
            'observers': 'Hold Ctrl/Cmd to select multiple observers',
            'deadline': 'Set the exact deadline date and time',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Import User here to avoid circular imports
        from users.models import User
        
        # Show all projects in dropdown
        if 'project' in self.fields:
            from projects.models import Projects
            self.fields['project'].queryset = Projects.objects.all()
            self.fields['project'].widget.attrs.update({'class': 'form-control'})
        
        # Only show employees for assignment
        if 'assigned_to' in self.fields:
            self.fields['assigned_to'].queryset = User.objects.filter(role='EMPLOYEE')
            self.fields['assigned_to'].widget.attrs.update({'class': 'form-control'})
            # Custom display: Show full name and username
            self.fields['assigned_to'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"
        
        # Show admins and team leads for assigned_by (task owner)
        if 'assigned_by' in self.fields:
            self.fields['assigned_by'].queryset = User.objects.filter(role__in=['ADMIN', 'TEAM_LEAD'])
            self.fields['assigned_by'].widget.attrs.update({'class': 'form-control'})
            self.fields['assigned_by'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"
            # Make it required
            self.fields['assigned_by'].required = True
        
        # Show all users for observers
        if 'observers' in self.fields:
            self.fields['observers'].queryset = User.objects.all()
            self.fields['observers'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"
        
        # Status field styling
        if 'status' in self.fields:
            self.fields['status'].widget.attrs.update({'class': 'form-control'})
        
        # Set initial value for assigned_by if not set (for new tasks)
        if not self.instance.pk and 'assigned_by' in self.fields:
            # You can set this to current user in the view instead
            pass

    def clean(self):
        """Custom validation"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        deadline = cleaned_data.get('deadline')
        
        # Validate that end_date is after start_date
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("End date cannot be before start date")
        
        # Validate that deadline is after start_date (if provided)
        if deadline and start_date:
            # Convert start_date to datetime with timezone awareness
            start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
            
            # Make it timezone-aware using Django's timezone
            if timezone.is_naive(start_datetime):
                start_datetime = timezone.make_aware(start_datetime)
            
            if deadline < start_datetime:
                raise forms.ValidationError("Deadline cannot be before start date")
        
        return cleaned_data