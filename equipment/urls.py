from django.urls import path
from equipment import views

app_name = 'equipment'

urlpatterns = [
    path('', views.available_equipment, name='available'),
    path('manifest/', views.manifest, name='manifest'),
    path('manifest/create/', views.create_equipment, name='create'),
    path('manifest/categories/', views.manage_category, name='manage_category'),
    path('manifest/<int:equipment_id>/edit/', views.edit_equipment, name='edit'),
    path('manifest/<int:equipment_id>/delete/', views.delete_equipment, name='delete'),
]
