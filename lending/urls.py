from django.urls import path
from lending import views

app_name = 'lending'

urlpatterns = [
    path('', views.my_requests, name='my_requests'),
    path('request/<int:equipment_id>/', views.create_request, name='create_request'),
    path('request/bulk/', views.create_bulk_request, name='create_bulk_request'),
    path('request/<int:request_id>/borrow-code/', views.borrow_code, name='borrow_code'),
    path('penalties/<int:penalty_id>/pay/', views.create_penalty_checkout, name='pay_penalty'),
    path('penalties/payment/success/', views.penalty_payment_success, name='penalty_payment_success'),
    path('penalties/payment/cancel/', views.penalty_payment_cancel, name='penalty_payment_cancel'),
    path('request/<int:request_id>/return/', views.request_return, name='request_return'),
    path('admin/', views.admin_requests, name='admin_requests'),
    path('admin/<int:request_id>/approve/', views.approve_request, name='approve'),
    path('admin/<int:request_id>/deny/', views.deny_request, name='deny'),
    path('admin/<int:request_id>/borrowed/', views.mark_borrowed, name='borrowed'),
    path('admin/<int:request_id>/returned/', views.mark_returned, name='returned'),
    path('overdue/', views.overdue_management, name='overdue'),
    path('penalties/<int:penalty_id>/update/', views.update_penalty, name='update_penalty'),
]
