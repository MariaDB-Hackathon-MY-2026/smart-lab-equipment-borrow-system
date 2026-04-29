from django.contrib import messages
from django.contrib.auth import login, logout
from django.db import transaction
from django.shortcuts import redirect, render

from .decorators import user_required
from .forms import LoginForm, UserRegistrationForm


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard:overview')
        return redirect('user-dashboard')

    login_form = LoginForm(request=request)
    register_form = UserRegistrationForm()
    active_panel = 'login'

    if request.method == 'POST':
        action = request.POST.get('action', 'login')

        if action == 'register':
            register_form = UserRegistrationForm(request.POST)
            login_form = LoginForm(request=request)
            active_panel = 'register'

            if register_form.is_valid():
                with transaction.atomic():
                    register_form.save()
                messages.success(request, 'Registration successful. You can now sign in with your new account.')
                return redirect('login')
        else:
            login_form = LoginForm(request=request, data=request.POST)
            register_form = UserRegistrationForm()
            active_panel = 'login'

            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                if user.is_staff or user.is_superuser:
                    return redirect('/dashboard/')
                return redirect('/user/dashboard/')

    return render(
        request,
        'registration/login.html',
        {
            'form': login_form,
            'register_form': register_form,
            'active_panel': active_panel,
        },
    )


def logout_view(request):
    logout(request)
    return redirect('login')


@user_required
def user_dashboard(request):
    member = getattr(request.user, 'member', None)
    return render(request, 'user_dashboard.html', {'member': member})
