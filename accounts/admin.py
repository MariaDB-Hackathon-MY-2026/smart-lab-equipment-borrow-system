from django.contrib import admin
from accounts.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'student_or_staff_id', 'phone_number', 'is_active')
    list_filter = ('role', 'is_active', 'department')
    search_fields = ('user__username', 'user__email', 'student_or_staff_id')

# Register your models here.
