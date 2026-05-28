from django.contrib import admin
from equipment.models import Equipment, EquipmentCategory


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('asset_tag', 'name', 'category', 'lab_location', 'status', 'daily_penalty_rate', 'is_active')
    list_filter = ('status', 'category', 'is_active')
    search_fields = ('asset_tag', 'name', 'serial_number', 'lab_location')

# Register your models here.
