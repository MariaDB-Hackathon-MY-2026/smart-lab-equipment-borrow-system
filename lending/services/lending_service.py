from decimal import Decimal
from django.db import connection, transaction
from django.utils.crypto import salted_hmac
from django.utils.dateparse import parse_date
from django.utils import timezone
from equipment.models import Equipment
from lending.models import LendingRequest, Penalty


class LendingService:
    BORROW_CODE_WINDOW_SECONDS = 300
    ACTIVE_REQUEST_STATUSES = [
        LendingRequest.STATUS_PENDING,
        LendingRequest.STATUS_APPROVED,
        LendingRequest.STATUS_BORROWED,
        LendingRequest.STATUS_RETURN_REQUESTED,
        LendingRequest.STATUS_OVERDUE,
    ]

    def _uses_mariadb(self):
        return connection.vendor == 'mysql' and getattr(connection, 'mysql_is_mariadb', False)

    def _clean_borrow_period(self, requested_from, requested_until):
        start_date = parse_date(requested_from or '')
        end_date = parse_date(requested_until or '')
        earliest_start = timezone.localdate() + timezone.timedelta(days=1)

        if not start_date or not end_date:
            raise ValueError('Borrow From and Borrow Until dates are required.')
        if start_date < earliest_start:
            raise ValueError('Borrow From must be at least 1 day from today.')
        if start_date.weekday() >= 5 or end_date.weekday() >= 5:
            raise ValueError('Borrow From and Borrow Until must be Monday to Friday.')
        if end_date < start_date:
            raise ValueError('Borrow Until must be the same date or later than Borrow From.')
        return start_date, end_date

    def list_all_requests(self):
        return LendingRequest.objects.select_related(
            'borrower',
            'equipment',
            'equipment__category',
            'penalty',
        ).all()

    def list_user_requests(self, user):
        return self.list_all_requests().filter(borrower=user)

    def list_pending_requests(self):
        return self.list_all_requests().filter(status=LendingRequest.STATUS_PENDING)

    def active_equipment_ids(self):
        return LendingRequest.objects.filter(
            status__in=self.ACTIVE_REQUEST_STATUSES,
        ).values_list('equipment_id', flat=True)

    def has_unpaid_penalties(self, user):
        return Penalty.objects.filter(
            lending_request__borrower=user,
            status=Penalty.STATUS_UNPAID,
        ).exists()

    def ensure_no_unpaid_penalties(self, user):
        if self.has_unpaid_penalties(user):
            raise ValueError('Please settle all penalties before borrowing new equipment.')

    def _borrow_code_window(self):
        return int(timezone.now().timestamp() // self.BORROW_CODE_WINDOW_SECONDS)

    def _borrow_code_payload(self, lending_request, window):
        approved_at_value = int(lending_request.approved_at.timestamp()) if lending_request.approved_at else 0
        return f'{lending_request.id}:{lending_request.borrower_id}:{lending_request.equipment_id}:{approved_at_value}:{window}'

    def borrow_code_for_request(self, lending_request):
        if lending_request.status != LendingRequest.STATUS_APPROVED:
            raise ValueError('Borrow code is only available for approved requests.')

        window = self._borrow_code_window()
        digest = salted_hmac(
            'lendr.borrow-code',
            self._borrow_code_payload(lending_request, window),
        ).hexdigest()
        code = str(int(digest, 16) % 1000000).zfill(6)
        remaining_seconds = self.BORROW_CODE_WINDOW_SECONDS - int(timezone.now().timestamp() % self.BORROW_CODE_WINDOW_SECONDS)
        return code, remaining_seconds

    def validate_borrow_code(self, lending_request, borrow_code):
        if not borrow_code:
            raise ValueError('Borrow code is required.')
        if lending_request.status != LendingRequest.STATUS_APPROVED:
            raise ValueError('Only approved requests can be borrowed.')

        expected_code, _ = self.borrow_code_for_request(lending_request)
        if str(borrow_code).strip() != expected_code:
            raise ValueError('Invalid borrow code.')

    def list_overdue_requests(self):
        today = timezone.localdate()
        return self.list_all_requests().filter(
            requested_until__lt=today,
            status__in=[LendingRequest.STATUS_APPROVED, LendingRequest.STATUS_BORROWED, LendingRequest.STATUS_OVERDUE],
        )

    def create_request(self, user, equipment_id, purpose, requested_from, requested_until):
        self.ensure_no_unpaid_penalties(user)
        equipment = Equipment.objects.get(id=equipment_id, is_active=True)
        start_date, end_date = self._clean_borrow_period(requested_from, requested_until)
        if LendingRequest.objects.filter(
            equipment_id=equipment.id,
            status__in=self.ACTIVE_REQUEST_STATUSES,
        ).exists():
            raise ValueError('This item already has an active borrowing request.')
        return LendingRequest.objects.create(
            borrower=user,
            equipment=equipment,
            purpose=purpose,
            requested_from=start_date,
            requested_until=end_date,
        )

    @transaction.atomic
    def create_bulk_requests(self, user, equipment_ids, purpose, requested_from, requested_until):
        self.ensure_no_unpaid_penalties(user)
        selected_ids = []
        for equipment_id in equipment_ids:
            try:
                parsed_id = int(equipment_id)
            except (TypeError, ValueError):
                raise ValueError('Please select valid equipment items.')
            if parsed_id not in selected_ids:
                selected_ids.append(parsed_id)

        purpose = (purpose or '').strip()
        start_date, end_date = self._clean_borrow_period(requested_from, requested_until)

        if not selected_ids:
            raise ValueError('Please select at least one equipment item.')
        if not purpose:
            raise ValueError('Purpose is required.')

        unavailable_ids = set(
            LendingRequest.objects.select_for_update().filter(
                equipment_id__in=selected_ids,
                status__in=self.ACTIVE_REQUEST_STATUSES,
            ).values_list('equipment_id', flat=True)
        )
        if unavailable_ids:
            raise ValueError('One or more selected items already have an active borrowing request.')

        equipments = list(
            Equipment.objects.select_for_update()
            .filter(id__in=selected_ids, is_active=True, status=Equipment.STATUS_AVAILABLE)
        )
        if len(equipments) != len(selected_ids):
            raise ValueError('One or more selected items are no longer available.')

        equipment_by_id = {equipment.id: equipment for equipment in equipments}
        requests = [
            LendingRequest(
                borrower=user,
                equipment=equipment_by_id[equipment_id],
                purpose=purpose,
                requested_from=start_date,
                requested_until=end_date,
            )
            for equipment_id in selected_ids
        ]
        return LendingRequest.objects.bulk_create(requests)

    def approve_request(self, request_id, admin_user, note=''):
        lending_request = LendingRequest.objects.select_related('equipment').get(id=request_id)
        lending_request.status = LendingRequest.STATUS_APPROVED
        lending_request.admin_note = note
        lending_request.approved_by = admin_user
        lending_request.approved_at = timezone.now()
        lending_request.save()
        return lending_request

    def deny_request(self, request_id, admin_user, note=''):
        lending_request = LendingRequest.objects.get(id=request_id)
        lending_request.status = LendingRequest.STATUS_DENIED
        lending_request.admin_note = note
        lending_request.approved_by = admin_user
        lending_request.approved_at = timezone.now()
        lending_request.save()
        return lending_request

    @transaction.atomic
    def mark_borrowed(self, request_id, borrow_code):
        lending_request = LendingRequest.objects.select_for_update().select_related('equipment').get(id=request_id)
        equipment = Equipment.objects.select_for_update().get(id=lending_request.equipment_id)
        self.validate_borrow_code(lending_request, borrow_code)
        if equipment.status != Equipment.STATUS_AVAILABLE:
            raise ValueError('Equipment is not available for checkout.')
        lending_request.status = LendingRequest.STATUS_BORROWED
        lending_request.borrowed_at = timezone.now()
        lending_request.save()
        equipment.status = Equipment.STATUS_BORROWED
        equipment.save(update_fields=['status'])
        return lending_request

    @transaction.atomic
    def request_return(self, user, request_id):
        lending_request = LendingRequest.objects.get(id=request_id, borrower=user)
        if lending_request.status not in [LendingRequest.STATUS_BORROWED, LendingRequest.STATUS_OVERDUE]:
            raise ValueError('Only borrowed equipment can be submitted for return.')
        lending_request.status = LendingRequest.STATUS_RETURN_REQUESTED
        lending_request.save(update_fields=['status', 'updated_at'])
        return lending_request

    @transaction.atomic
    def mark_returned(self, request_id, penalty_amount='0', penalty_note=''):
        lending_request = LendingRequest.objects.select_for_update().select_related('equipment').get(id=request_id)
        equipment = Equipment.objects.select_for_update().get(id=lending_request.equipment_id)
        if lending_request.status != LendingRequest.STATUS_RETURN_REQUESTED:
            raise ValueError('A return can only be completed after the borrower submits a return request.')

        try:
            penalty_amount = Decimal(penalty_amount or '0')
        except Exception:
            raise ValueError('Penalty amount must be a valid MYR amount.')
        if penalty_amount < Decimal('0.00'):
            raise ValueError('Penalty amount cannot be negative.')
        days_overdue = max((timezone.localdate() - lending_request.requested_until).days, 0)
        late_penalty_amount = Decimal(days_overdue) * lending_request.equipment.daily_penalty_rate
        total_penalty_amount = late_penalty_amount + penalty_amount
        if total_penalty_amount > Decimal('0.00'):
            penalty_note = (penalty_note or '').strip()
            note_parts = []
            if late_penalty_amount > Decimal('0.00'):
                note_parts.append(
                    f'Late penalty: RM {late_penalty_amount} ({days_overdue} day(s) x RM {lending_request.equipment.daily_penalty_rate}).'
                )
            if penalty_amount > Decimal('0.00'):
                note_parts.append(f'Product return penalty: RM {penalty_amount}.')
            if penalty_note:
                note_parts.append(f'Reason: {penalty_note}')
            Penalty.objects.update_or_create(
                lending_request=lending_request,
                defaults={
                    'days_overdue': days_overdue,
                    'amount': total_penalty_amount,
                    'product_penalty_amount': penalty_amount,
                    'status': Penalty.STATUS_UNPAID,
                    'note': ' '.join(note_parts),
                },
            )

        lending_request.status = LendingRequest.STATUS_RETURNED
        lending_request.returned_at = timezone.now()
        lending_request.save()
        equipment.status = Equipment.STATUS_AVAILABLE
        equipment.save(update_fields=['status'])
        return lending_request

    def refresh_overdue_and_penalties(self):
        if self._uses_mariadb():
            with connection.cursor() as cursor:
                cursor.execute('CALL sp_refresh_overdue_penalties()')
            return self.list_overdue_requests()

        today = timezone.localdate()
        overdue_requests = self.list_overdue_requests()
        for lending_request in overdue_requests:
            days_overdue = max((today - lending_request.requested_until).days, 0)
            late_penalty_amount = Decimal(days_overdue) * lending_request.equipment.daily_penalty_rate
            lending_request.status = LendingRequest.STATUS_OVERDUE
            lending_request.save(update_fields=['status'])
            penalty, _created = Penalty.objects.get_or_create(
                lending_request=lending_request,
                defaults={
                    'days_overdue': days_overdue,
                    'amount': late_penalty_amount,
                    'product_penalty_amount': Decimal('0.00'),
                    'status': Penalty.STATUS_UNPAID,
                    'note': f'Late penalty: RM {late_penalty_amount} ({days_overdue} day(s) x RM {lending_request.equipment.daily_penalty_rate}).',
                },
            )
            if penalty.status == Penalty.STATUS_UNPAID:
                product_penalty_amount = penalty.product_penalty_amount or Decimal('0.00')
                penalty.days_overdue = days_overdue
                penalty.amount = late_penalty_amount + product_penalty_amount
                penalty.note = f'Late penalty: RM {late_penalty_amount} ({days_overdue} day(s) x RM {lending_request.equipment.daily_penalty_rate}).'
                if product_penalty_amount > Decimal('0.00'):
                    penalty.note += f' Product return penalty: RM {product_penalty_amount}.'
                penalty.save(update_fields=['days_overdue', 'amount', 'note', 'updated_at'])
        return overdue_requests

    def list_penalties_for_user(self, user):
        return Penalty.objects.select_related('lending_request', 'lending_request__equipment').filter(
            lending_request__borrower=user
        )

    def list_all_penalties(self):
        return Penalty.objects.select_related('lending_request', 'lending_request__borrower', 'lending_request__equipment')

    def update_penalty_status(self, penalty_id, status):
        penalty = Penalty.objects.get(id=penalty_id)
        if penalty.status != Penalty.STATUS_UNPAID:
            raise ValueError('This penalty has already been settled and cannot be changed.')
        if status not in [Penalty.STATUS_PAID, Penalty.STATUS_WAIVED]:
            raise ValueError('Unpaid penalties can only be marked as paid or waived.')
        penalty.status = status
        penalty.save(update_fields=['status'])
        return penalty

    def mark_penalty_paid(self, penalty_id, user):
        penalty = self.list_penalties_for_user(user).get(id=penalty_id)
        penalty.status = Penalty.STATUS_PAID
        penalty.save(update_fields=['status', 'updated_at'])
        return penalty
