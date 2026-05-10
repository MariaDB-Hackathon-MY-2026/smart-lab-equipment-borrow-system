from django.core.management.base import BaseCommand
from django.utils import timezone

from lending.models import LendingRequest, Penalty
from lending.services.lending_service import LendingService
from lending.services.notification_service import LendingNotificationService


class Command(BaseCommand):
    help = 'Refresh overdue penalties and send daily lending reminders.'

    def handle(self, *args, **options):
        lending_service = LendingService()
        notification_service = LendingNotificationService()

        lending_service.refresh_overdue_and_penalties()

        today = timezone.localdate()
        reminder_count = 0
        for days_until in [2, 1, 0]:
            due_date = today + timezone.timedelta(days=days_until)
            requests = lending_service.list_all_requests().filter(
                requested_until=due_date,
                status__in=[
                    LendingRequest.STATUS_APPROVED,
                    LendingRequest.STATUS_BORROWED,
                ],
            )
            for lending_request in requests:
                notification_service.return_due_reminder(lending_request, days_until)
                reminder_count += 1

        penalty_count = 0
        penalties = Penalty.objects.select_related(
            'lending_request',
            'lending_request__borrower',
            'lending_request__equipment',
        ).filter(status=Penalty.STATUS_UNPAID)
        for penalty in penalties:
            notification_service.unpaid_penalty_reminder(penalty)
            penalty_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Sent {reminder_count} return reminder(s) and {penalty_count} unpaid penalty reminder(s).'
        ))
