from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from dashboard import views as dashboard_views


def root_redirect(request):
    return redirect('/accounts/login/')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('admin-dashboard/', dashboard_views.admin_dashboard, name='admin-dashboard'),
    path('', root_redirect, name='root'),
]
