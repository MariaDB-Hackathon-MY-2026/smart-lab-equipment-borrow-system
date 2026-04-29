from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import include, path
from dashboard import views as dashboard_views
from lendr_project import views as lendr_views


def root_redirect(request):
    return redirect('/accounts/login/')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', lendr_views.login_view, name='login'),
    path('accounts/logout/', lendr_views.logout_view, name='logout'),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('admin-dashboard/', dashboard_views.admin_dashboard, name='admin-dashboard'),
    path('user/dashboard/', lendr_views.user_dashboard, name='user-dashboard'),
    path('', root_redirect, name='root'),
]
