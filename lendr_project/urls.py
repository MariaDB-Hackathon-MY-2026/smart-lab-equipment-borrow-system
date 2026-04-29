from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import TemplateView


def root_redirect(request):
    return redirect('/accounts/login/')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('dashboard/', login_required(TemplateView.as_view(template_name='dashboard.html')), name='dashboard'),
    path('', root_redirect, name='root'),
]
