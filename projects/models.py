from django.db import models
from users.models import User


class Projects(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField()
    assigned_to = models.ManyToManyField(
        User,
        blank=True,
        related_name="projects") 
    start_date = models.DateField()
    end_date = models.DateField()
    
    updated_by = models.ForeignKey(
        'users.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='projects_updated'
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='projects_created'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name
    
    class Meta:
        permissions = [
            ("view_all_projects", "Can view all projects"),
        ]

    
class ProjectResource(models.Model):
    RESOURCE_TYPE_CHOICES = [
        ('TEXT', 'Text'),
        ('PDF', 'PDF'),
        ('IMAGE', 'Image'),
        ('LINK', 'Link'),
    ]
    
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='resources')
    resource_type = models.CharField(max_length=10, choices=RESOURCE_TYPE_CHOICES, blank=True, null=True)
    title = models.CharField(max_length=255)
    text_content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='project_resources/', blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.project.name} - {self.title} ({self.resource_type})"