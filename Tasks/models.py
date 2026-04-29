from django.db import models
from django.utils import timezone
import datetime


from users.models import User
from projects.models import Projects

class Task(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
    )

    name = models.CharField(max_length=100)  
    description = models.TextField()        
    project = models.ForeignKey(Projects, on_delete=models.CASCADE)  
    assigned_to = models.ManyToManyField(User, related_name='assigned_tasks')  
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

   
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    total_time = models.DurationField(null=True, blank=True)

   
    updated_by = models.ForeignKey(
        'users.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tasks_updated'
    )

    
    assigned_by = models.ManyToManyField(
        User, 
        related_name='created_tasks'
    ) 

    estimated_time = models.IntegerField(default=3600, help_text="Estimated time in seconds")

    created_at = models.DateTimeField(auto_now_add=True)  

    paused_time = models.DateTimeField(null=True, blank=True)  

    total_paused_duration = models.DurationField(default=datetime.timedelta())  
    
    deadline = models.DateTimeField(null=True, blank=True)  
    
    observers = models.ManyToManyField(
        User, 
        related_name='observing_tasks', 
        blank=True
    )  
   
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

