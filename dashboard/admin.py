from django.contrib import admin
from datetime import date, timedelta

from .models import Borrow, Equipment, Member


def add_weekdays(start_date, weekdays):
    current_date = start_date
    remaining = weekdays

    while remaining:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5:
            remaining -= 1

    return current_date


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('member_id', 'get_full_name', 'phone', 'created_at')
    search_fields = ('member_id', 'user__first_name', 'user__last_name', 'user__email')
    list_select_related = ('user',)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'serial_number', 'status', 'daily_penalty')
    list_filter = ('status', 'category')
    search_fields = ('name', 'category', 'serial_number')


@admin.register(Borrow)
class BorrowAdmin(admin.ModelAdmin):
    list_display = ('member', 'equipment', 'borrow_date', 'due_date', 'return_date', 'status', 'penalty')
    list_filter = ('status', 'borrow_date', 'due_date')
    search_fields = ('member__member_id', 'member__user__first_name', 'member__user__last_name', 'equipment__name')
    list_select_related = ('member__user', 'equipment')
    actions = ('approve_requests', 'reject_requests')

    @admin.action(description='Approve selected pending requests')
    def approve_requests(self, request, queryset):
        approved = 0
        for borrow in queryset.filter(status='Pending').select_related('equipment'):
            if borrow.equipment.status != 'available':
                continue
            approved_date = date.today()
            due_date = add_weekdays(approved_date, 5)
            borrow.status = 'Active'
            borrow.borrow_date = approved_date
            borrow.due_date = due_date
            borrow.return_date = due_date
            borrow.save(update_fields=['status', 'borrow_date', 'due_date', 'return_date'])
            borrow.equipment.status = 'borrowed'
            borrow.equipment.save(update_fields=['status'])
            approved += 1
        self.message_user(request, f'{approved} request(s) approved.')

    @admin.action(description='Reject selected pending requests')
    def reject_requests(self, request, queryset):
        updated = queryset.filter(status='Pending').update(status='Rejected')
        self.message_user(request, f'{updated} request(s) rejected.')
