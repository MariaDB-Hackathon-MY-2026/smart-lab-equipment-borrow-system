from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.admin_dashboard, name='overview'),
    path('admin/', views.admin_dashboard, name='admin_overview'),
    path('equipment/', views.equipment_management, name='equipment_management'),
    path('borrowings/', views.borrowing_records, name='borrowings'),
    path('overdue/', views.overdue_records, name='overdue'),
    path('analytics/', views.analytics, name='analytics'),
    path('equipment/<int:equipment_id>/edit/', views.edit_equipment, name='edit_equipment'),
    path('equipment/<int:equipment_id>/history/', views.equipment_history, name='equipment_history'),
    path('equipment/<int:equipment_id>/deactivate/', views.deactivate_equipment, name='deactivate_equipment'),
    path('requests/<int:borrow_id>/approve/', views.approve_borrow_request, name='approve_request'),
    path('requests/<int:borrow_id>/reject/', views.reject_borrow_request, name='reject_request'),
    path('requests/<int:borrow_id>/verify-return/', views.verify_return_request, name='verify_return_request'),
]
