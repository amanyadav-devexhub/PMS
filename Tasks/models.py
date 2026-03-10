# from django.db import models

# # Create your models here.
# from users.models import User
# from projects.models import Projects

# class Task(models.Model):
#     STATUS_CHOICES = (
#         ('PENDING', 'Pending'),
#         ('ONGOING', 'Ongoing'),
#         ('COMPLETED', 'Completed'),
#     )

#     name = models.CharField(max_length=100)  # Task title
#     description = models.TextField()          # Details about the task
#     project = models.ForeignKey(Projects, on_delete=models.CASCADE)  # Link to project
#     assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)  # Employee responsible
#     start_date = models.DateField()
#     end_date = models.DateField()
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

#      # NEW FIELDS FOR TIMER
#     start_time = models.DateTimeField(null=True, blank=True)
#     end_time = models.DateTimeField(null=True, blank=True)
#     total_time = models.DurationField(null=True, blank=True)




#     def __str__(self):
#         return self.name



# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

class Task(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ONGOING', 'In Progress'),
        ('COMPLETED', 'Completed'),
    ]
    
    # Basic Information
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Relationships
    project = models.ForeignKey('Project', on_delete=models.CASCADE, null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    
    # Dates and Times
    created_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField(null=True, blank=True)
    
    # Time Tracking Fields
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_paused_seconds = models.IntegerField(default=0)  # Track total paused time
    total_time_spent = models.CharField(max_length=20, null=True, blank=True)  # Format: "HH:MM:SS"
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Optional: Observers (Many-to-Many relationship)
    observers = models.ManyToManyField(User, related_name='observing_tasks', blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_time_spent_display(self):
        """Return formatted time spent"""
        if self.total_time_spent:
            return self.total_time_spent
        return "00:00:00"
    
    def calculate_progress(self):
        """Calculate progress percentage (assuming 2 hours estimated time)"""
        estimated_seconds = 7200  # 2 hours in seconds
        
        if self.status == 'COMPLETED' and self.total_time_spent:
            try:
                h, m, s = map(int, self.total_time_spent.split(':'))
                elapsed_seconds = h * 3600 + m * 60 + s
                return min(100, int((elapsed_seconds / estimated_seconds) * 100))
            except:
                return 100
        
        elif self.status == 'ONGOING' and self.started_at:
            elapsed = timezone.now() - self.started_at
            # Subtract paused time if any
            elapsed_seconds = elapsed.total_seconds() - self.total_paused_seconds
            return min(100, int((elapsed_seconds / estimated_seconds) * 100))
        
        return 0