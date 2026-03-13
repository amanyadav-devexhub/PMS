from functools import wraps
from django.shortcuts import redirect

def allowed_roles(allowed_roles=[]):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser or request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            return redirect("login_page")
        return wrapper
    return decorator