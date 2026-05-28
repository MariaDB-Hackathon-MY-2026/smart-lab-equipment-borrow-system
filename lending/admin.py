from django.contrib import admin
from lending.models import LendingRequest, Penalty


@admin.register(LendingRequest)
class LendingRequestAdmin(admin.ModelAdmin):
    list_display = ('borrower', 'equipment', 'requested_from', 'requested_until', 'status', 'created_at')
    list_filter = ('status', 'requested_from', 'requested_until')
    search_fields = ('borrower__username', 'equipment__name', 'equipment__asset_tag')


@admin.register(Penalty)
class PenaltyAdmin(admin.ModelAdmin):
    list_display = ('lending_request', 'amount', 'days_overdue', 'status', 'created_at')
    list_filter = ('status',)

# Register your models here.
