from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.admin_dashboard, name='overview'),
    path('admin/', views.admin_dashboard, name='admin_overview'),
    path('requests/<int:borrow_id>/approve/', views.approve_borrow_request, name='approve_request'),
    path('requests/<int:borrow_id>/reject/', views.reject_borrow_request, name='reject_request'),
]
