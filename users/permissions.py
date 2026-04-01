def _has(user, perm_name):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(perm_name)


def has_any(user, perm_names):
    return any(_has(user, perm_name) for perm_name in perm_names)


def can_manage_users(user):
    return has_any(user, [
        'users.view_user',
        'users.add_user',
        'users.change_user',
        'users.delete_user',
    ])


def can_manage_roles(user):
    return has_any(user, [
        'users.view_role',
        'users.add_role',
        'users.change_role',
        'users.delete_role',
    ])


def can_manage_org(user):
    return has_any(user, [
        'users.add_department',
        'users.change_department',
        'users.delete_department',
        'users.add_designation',
        'users.change_designation',
        'users.delete_designation',
    ])


def can_view_projects(user):
    return has_any(user, ['projects.view_projects']) or can_manage_projects(user)


def can_add_projects(user):
    return has_any(user, ['projects.add_projects'])


def can_change_projects(user):
    return has_any(user, ['projects.change_projects'])


def can_delete_projects(user):
    return has_any(user, ['projects.delete_projects'])


def can_manage_projects(user):
    return can_add_projects(user) or can_change_projects(user) or can_delete_projects(user)


def can_view_all_projects(user):
    return can_manage_projects(user) or can_manage_users(user)


def can_add_task(user):
    return has_any(user, ['Tasks.add_task', 'tasks.add_task'])


def can_change_task(user):
    return has_any(user, ['Tasks.change_task', 'tasks.change_task'])


def can_delete_task(user):
    return has_any(user, ['Tasks.delete_task', 'tasks.delete_task'])


def can_view_task(user):
    return has_any(user, ['Tasks.view_task', 'tasks.view_task']) or can_change_task(user)


def can_manage_all_tasks(user):
    return can_manage_users(user) or can_manage_projects(user) or can_delete_task(user)


def can_view_all_tasks(user):
    return can_manage_all_tasks(user)


def is_manager_like(user):
    return can_add_task(user) or can_manage_projects(user) or can_manage_users(user)


def is_contributor_like(user):
    return can_view_task(user) and not is_manager_like(user)


def dashboard_url_for(user):
    if can_manage_users(user):
        return '/admin_dashboard/'
    if can_add_task(user):
        return '/teamlead_dashboard/'
    if can_view_task(user):
        return '/employee_dashboard/'
    return '/dashboard/'
