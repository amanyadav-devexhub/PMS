from django.db import models
from django.utils import timezone
import datetime

# Create your models here.
from users.models import User
from projects.models import Projects

class Task(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
    )

    name = models.CharField(max_length=100)  # Task title
    description = models.TextField()          # Details about the task
    project = models.ForeignKey(Projects, on_delete=models.CASCADE)  # Link to project
    assigned_to = models.ManyToManyField(User, related_name='assigned_tasks')  # Employee responsible
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

     # NEW FIELDS FOR TIMER
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    total_time = models.DurationField(null=True, blank=True)

    # Add with your other fields
    updated_by = models.ForeignKey(
        'users.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tasks_updated'
    )

    ## new fields
    assigned_by = models.ManyToManyField(
        User, 
        related_name='created_tasks'
    ) ## who created/assigned the task

    estimated_time = models.IntegerField(default=3600, help_text="Estimated time in seconds")

    created_at = models.DateTimeField(auto_now_add=True)  # Auto-set when task is created

    paused_time = models.DateTimeField(null=True, blank=True)  # When task was paused

    total_paused_duration = models.DurationField(default=datetime.timedelta())  # Total paused time
    
    deadline = models.DateTimeField(null=True, blank=True)  # Exact deadline with time
    
    observers = models.ManyToManyField(
        User, 
        related_name='observing_tasks', 
        blank=True
    )  # Users watching this task
    ## summary
    summary = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True, related_name='tasks_created')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        permissions = [
            ("view_all_tasks", "Can view all tasks"),
        ]

