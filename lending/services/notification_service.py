from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db.models import Q

from accounts.models import UserProfile
from lending.models import Penalty


class LendingNotificationService:
    def _recipient_email(self, user):
        return (getattr(user, 'email', '') or '').strip()

    def _admin_emails(self):
        admins = User.objects.filter(
            Q(is_staff=True) |
            Q(is_superuser=True) |
            Q(userprofile__role=UserProfile.ROLE_ADMIN) |
            Q(groups__name='Admin')
        ).distinct()
        return [email for email in (self._recipient_email(user) for user in admins) if email]

    def _send(self, subject, message, recipients):
        recipients = [email for email in dict.fromkeys(recipients) if email]
        if not recipients:
            return 0
        return send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=True,
        )

    def borrowing_request_submitted(self, lending_requests):
        lending_requests = list(lending_requests)
        if not lending_requests:
            return
        borrower = lending_requests[0].borrower
        item_lines = '\n'.join(
            f"- {request.equipment.name} ({request.equipment.asset_tag}), {request.requested_from} to {request.requested_until}"
            for request in lending_requests
        )
        user_message = (
            f"Hi {borrower.username},\n\n"
            "Your borrowing request has been submitted for administrator review.\n\n"
            f"{item_lines}\n\n"
            "You will receive another email once it is approved."
        )
        admin_message = (
            "A new borrowing request has been submitted.\n\n"
            f"Borrower: {borrower.username}\n"
            f"Email: {borrower.email or '-'}\n\n"
            f"{item_lines}"
        )
        self._send('Lendr borrowing request submitted', user_message, [self._recipient_email(borrower)])
        self._send('New Lendr borrowing request', admin_message, self._admin_emails())

    def borrowing_request_approved(self, lending_request):
        borrower = lending_request.borrower
        message = (
            f"Hi {borrower.username},\n\n"
            "Your borrowing request has been approved.\n\n"
            f"Equipment: {lending_request.equipment.name} ({lending_request.equipment.asset_tag})\n"
            f"Borrowing period: {lending_request.requested_from} to {lending_request.requested_until}\n\n"
            "Please collect the equipment using your Borrow Key in Lendr."
        )
        self._send('Lendr borrowing request approved', message, [self._recipient_email(borrower)])

    def return_due_reminder(self, lending_request, days_until):
        borrower = lending_request.borrower
        if days_until == 0:
            timing = 'today'
        elif days_until == 1:
            timing = 'tomorrow'
        else:
            timing = f'in {days_until} days'
        message = (
            f"Hi {borrower.username},\n\n"
            f"This is a reminder that {lending_request.equipment.name} ({lending_request.equipment.asset_tag}) "
            f"is due for return {timing}, on {lending_request.requested_until}.\n\n"
            "Please return it on time to avoid late penalties."
        )
        self._send('Lendr return reminder', message, [self._recipient_email(borrower)])

    def return_completed(self, lending_request):
        borrower = lending_request.borrower
        try:
            penalty = lending_request.penalty
        except ObjectDoesNotExist:
            penalty = None
        penalty_text = 'No penalties were applied.'
        if penalty:
            penalty_text = (
                f"Penalty status: {penalty.get_status_display()}\n"
                f"Penalty amount: RM {penalty.amount}\n"
                f"Reason: {penalty.note or '-'}"
            )
        message = (
            f"Hi {borrower.username},\n\n"
            f"Your return for {lending_request.equipment.name} ({lending_request.equipment.asset_tag}) has been completed.\n\n"
            f"{penalty_text}"
        )
        self._send('Lendr return completed', message, [self._recipient_email(borrower)])

    def penalty_status_changed(self, penalty):
        borrower = penalty.lending_request.borrower
        message = (
            f"Hi {borrower.username},\n\n"
            f"Your penalty for {penalty.lending_request.equipment.name} has been marked as {penalty.get_status_display()}.\n\n"
            f"Amount: RM {penalty.amount}\n"
            f"Reason: {penalty.note or '-'}"
        )
        self._send(f'Lendr penalty {penalty.get_status_display().lower()}', message, [self._recipient_email(borrower)])

    def unpaid_penalty_reminder(self, penalty):
        borrower = penalty.lending_request.borrower
        if penalty.status != Penalty.STATUS_UNPAID:
            return
        message = (
            f"Hi {borrower.username},\n\n"
            "You have an unpaid Lendr penalty.\n\n"
            f"Equipment: {penalty.lending_request.equipment.name}\n"
            f"Amount due: RM {penalty.amount}\n"
            f"Reason: {penalty.note or '-'}\n\n"
            "Please pay the penalty in Lendr to restore borrowing access."
        )
        self._send('Lendr unpaid penalty reminder', message, [self._recipient_email(borrower)])
