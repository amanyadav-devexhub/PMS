from django.db import models
from users.models import User

# Create your models here.

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
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    # ## resource field
    # resource_text = models.TextField(
    #     blank=True,
    #     null=True,
    #     help_text="Notes or reference text"
    # )

    # resource_link = models.URLField(
    #     blank=True,
    #     null=True,
    #     help_text="Reference URL"
    # )

    # resource_file = models.FileField(
    #     upload_to='project_resources/',
    #     blank=True,
    #     null=True
    # )

    def __str__(self):
        return self.name
    
    
## ProjectResource Model
class ProjectResource(models.Model):
    RESOURCE_TYPE_CHOICES = [
        ('TEXT', 'Text'),
        ('PDF', 'PDF'),
        ('IMAGE', 'Image'),
        ('LINK', 'Link'),
    ]
    
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='resources')
    resource_type = models.CharField(max_length=10, choices=RESOURCE_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    text_content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='project_resources/', blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.project.name} - {self.title} ({self.resource_type})"