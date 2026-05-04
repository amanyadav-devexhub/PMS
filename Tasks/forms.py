
from django import forms
from .models import Task  
from projects.models import Projects  
from django.utils import timezone
import datetime

class TaskForm(forms.ModelForm):
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    
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
            'assigned_by',  
            'status',
            'start_date',
            'end_date',
            'deadline',     
            'observers',
            'summary',
            'estimated_time',     
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
        
       
        from users.models import User
        from users.permissions import can_view_task, is_manager_like
        
       
        if 'project' in self.fields:
            from projects.models import Projects
            self.fields['project'].queryset = Projects.objects.all()
            self.fields['project'].widget.attrs.update({'class': 'form-control'})
        
        
        if 'assigned_to' in self.fields:
            candidate_users = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True)
            contributor_ids = [candidate.id for candidate in candidate_users if can_view_task(candidate) and not is_manager_like(candidate)]
            self.fields['assigned_to'].queryset = User.objects.filter(id__in=contributor_ids)
            self.fields['assigned_to'].widget.attrs.update({'class': 'form-control'})
            
            self.fields['assigned_to'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"
        
      
        if 'assigned_by' in self.fields:
            candidate_users = User.objects.filter(is_active=True)
            manager_ids = [candidate.id for candidate in candidate_users if is_manager_like(candidate)]
            self.fields['assigned_by'].queryset = User.objects.filter(id__in=manager_ids)
            self.fields['assigned_by'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"
        
      
        if 'observers' in self.fields:
            self.fields['observers'].queryset = User.objects.all()
            self.fields['observers'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"
        
       
        if 'status' in self.fields:
            self.fields['status'].widget.attrs.update({'class': 'form-control'})
        
       
        if not self.instance.pk and 'assigned_by' in self.fields:
            
            pass

        def clean(self):
            cleaned_data = super().clean()
            start_date = cleaned_data.get('start_date')
            end_date = cleaned_data.get('end_date')
            deadline = cleaned_data.get('deadline')

            now = timezone.now()

            
            if start_date and start_date < now.date():
                raise forms.ValidationError("Start date cannot be in the past.")

           
            if end_date and end_date < now.date():
                raise forms.ValidationError("End date cannot be in the past.")

           
            if start_date and end_date and end_date < start_date:
                raise forms.ValidationError("End date cannot be before start date.")

            
            if deadline:
                if start_date:
                    start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
                    if timezone.is_naive(start_datetime):
                        start_datetime = timezone.make_aware(start_datetime)

                    if deadline < start_datetime:
                        raise forms.ValidationError("Deadline cannot be before start date.")
               
                if deadline < now:
                    raise forms.ValidationError("Deadline cannot be in the past.")

                if end_date:
                    end_datetime = datetime.datetime.combine(end_date, datetime.time.max)
                    if timezone.is_naive(end_datetime):
                        end_datetime = timezone.make_aware(end_datetime)

                    if deadline > end_datetime:
                        raise forms.ValidationError("Deadline cannot be after end date.")

            return cleaned_data