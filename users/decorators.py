from functools import wraps
from django.shortcuts import redirect

def allowed_roles(allowed_roles=[]):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login_page")  # your login page

            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)

            # logged in but wrong role
            return redirect("login_page")  # or a 403 page
        return wrapper
    return decorator