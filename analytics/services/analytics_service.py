from django.db.models import Count, Sum
from equipment.models import Equipment
from lending.models import LendingRequest, Penalty


class AnalyticsService:
    def dashboard_stats(self):
        penalty_total = Penalty.objects.filter(status=Penalty.STATUS_UNPAID).aggregate(total=Sum('amount'))['total'] or 0
        return {
            'equipment_total': Equipment.objects.filter(is_active=True).count(),
            'available_total': Equipment.objects.filter(is_active=True, status=Equipment.STATUS_AVAILABLE).count(),
            'pending_total': LendingRequest.objects.filter(status=LendingRequest.STATUS_PENDING).count(),
            'overdue_total': LendingRequest.objects.filter(status=LendingRequest.STATUS_OVERDUE).count(),
            'unpaid_penalty_total': penalty_total,
        }

    def request_status_counts(self):
        return list(
            LendingRequest.objects.values('status').annotate(total=Count('id')).order_by('status')
        )

    def equipment_status_counts(self):
        return list(
            Equipment.objects.filter(is_active=True).values('status').annotate(total=Count('id')).order_by('status')
        )
