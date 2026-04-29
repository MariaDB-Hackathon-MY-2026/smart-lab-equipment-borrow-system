from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def admin_required(view_func):
    @login_required(login_url='login')
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        return redirect('user-dashboard')

    return _wrapped_view


def user_required(view_func):
    @login_required(login_url='login')
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard:overview')
        return view_func(request, *args, **kwargs)

    return _wrapped_view
