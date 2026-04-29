from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Task

@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def update_project_status(sender, instance, **kwargs):

    project = instance.project
    if not project:
        return

    tasks = project.task_set.all()
    if not tasks.exists():
        if project.status != 'PENDING':
            project.status = 'PENDING'
            project.save(update_fields=['status'])
        return

    has_ongoing = tasks.filter(status='ONGOING').exists()
    has_pending = tasks.filter(status='PENDING').exists()
    all_completed = tasks.exists() and not (has_ongoing or has_pending)

    if has_ongoing:
        if project.status != 'ONGOING':
            project.status = 'ONGOING'
            project.save(update_fields=['status'])
    
    elif all_completed:
        if project.status != 'COMPLETED':
            project.status = 'COMPLETED'
            project.save(update_fields=['status'])
            
    elif has_pending:
        if project.status == 'COMPLETED':
            project.status = 'ONGOING'
            project.save(update_fields=['status'])
