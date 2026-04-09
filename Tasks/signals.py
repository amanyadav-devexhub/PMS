from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Task

@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def update_project_status(sender, instance, **kwargs):
    """
    Automates project status based on task statuses:
    1. If any task is ONGOING -> Project is ONGOING.
    2. If all tasks are COMPLETED -> Project is COMPLETED.
    3. If a new task (PENDING) is added to a COMPLETED project -> Project becomes ONGOING.
    4. If no tasks exist -> Project reverts to PENDING.
    """
    project = instance.project
    if not project:
        return

    # Use all() to get the current state of tasks
    tasks = project.task_set.all()
    
    if not tasks.exists():
        if project.status != 'PENDING':
            project.status = 'PENDING'
            project.save(update_fields=['status'])
        return

    has_ongoing = tasks.filter(status='ONGOING').exists()
    has_pending = tasks.filter(status='PENDING').exists()
    all_completed = tasks.exists() and not (has_ongoing or has_pending)

    # Logic:
    # If there is at least one ongoing task, the project is definitely ongoing.
    if has_ongoing:
        if project.status != 'ONGOING':
            project.status = 'ONGOING'
            project.save(update_fields=['status'])
    
    # If all tasks are completed, the project is completed.
    elif all_completed:
        if project.status != 'COMPLETED':
            project.status = 'COMPLETED'
            project.save(update_fields=['status'])
            
    # If there are pending tasks but none are ongoing:
    # - If the project was COMPLETED, it must move to ONGOING because a new task was likely added.
    # - If the project was PENDING, it stays PENDING until something starts.
    elif has_pending:
        if project.status == 'COMPLETED':
            project.status = 'ONGOING'
            project.save(update_fields=['status'])
