from django.test import SimpleTestCase, TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from unittest.mock import Mock, patch
from decimal import Decimal
from equipment.models import Equipment, EquipmentCategory
from lending.models import LendingRequest, Penalty
from lending.services.lending_service import LendingService


class ReturnRequestTests(SimpleTestCase):
    def test_return_requested_status_keeps_equipment_active(self):
        self.assertIn(
            LendingRequest.STATUS_RETURN_REQUESTED,
            LendingService.ACTIVE_REQUEST_STATUSES,
        )

    @patch.object(LendingService, 'has_unpaid_penalties', return_value=True)
    def test_unpaid_penalties_block_new_borrowing(self, _mock_has_unpaid_penalties):
        service = LendingService()

        with self.assertRaisesMessage(ValueError, 'Please settle all penalties before borrowing new equipment.'):
            service.ensure_no_unpaid_penalties(Mock())

    @patch.object(LendingService, 'has_unpaid_penalties', return_value=False)
    def test_no_unpaid_penalties_allows_borrowing_guard(self, _mock_has_unpaid_penalties):
        service = LendingService()

        self.assertIsNone(service.ensure_no_unpaid_penalties(Mock()))


class PenaltyStatusUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='borrower', password='pass')
        category = EquipmentCategory.objects.create(name='VR Headsets')
        equipment = Equipment.objects.create(
            asset_tag='VR-1',
            name='Meta Quest 3',
            category=category,
            lab_location='FCDT Office',
            serial_number='SN-1',
        )
        self.lending_request = LendingRequest.objects.create(
            borrower=self.user,
            equipment=equipment,
            purpose='FYP',
            requested_from='2026-05-11',
            requested_until='2026-05-12',
            status=LendingRequest.STATUS_RETURNED,
        )
        self.penalty = Penalty.objects.create(
            lending_request=self.lending_request,
            amount='10.00',
            days_overdue=1,
            status=Penalty.STATUS_UNPAID,
        )

    def test_admin_can_mark_unpaid_penalty_paid(self):
        LendingService().update_penalty_status(self.penalty.id, Penalty.STATUS_PAID)

        self.penalty.refresh_from_db()
        self.assertEqual(self.penalty.status, Penalty.STATUS_PAID)

    def test_admin_cannot_change_settled_penalty(self):
        self.penalty.status = Penalty.STATUS_PAID
        self.penalty.save(update_fields=['status'])

        with self.assertRaisesMessage(ValueError, 'This penalty has already been settled and cannot be changed.'):
            LendingService().update_penalty_status(self.penalty.id, Penalty.STATUS_WAIVED)

    def test_return_penalty_combines_late_and_product_penalties(self):
        self.lending_request.status = LendingRequest.STATUS_RETURN_REQUESTED
        self.lending_request.requested_until = timezone.localdate() - timezone.timedelta(days=2)
        self.lending_request.equipment.daily_penalty_rate = Decimal('5.00')
        self.lending_request.equipment.save(update_fields=['daily_penalty_rate'])
        self.lending_request.save(update_fields=['status', 'requested_until'])
        self.penalty.delete()

        LendingService().mark_returned(self.lending_request.id, '7.50', 'Cracked casing')

        penalty = Penalty.objects.get(lending_request=self.lending_request)
        self.assertEqual(penalty.days_overdue, 2)
        self.assertEqual(penalty.product_penalty_amount, Decimal('7.50'))
        self.assertEqual(penalty.amount, Decimal('17.50'))
        self.assertIn('Late penalty', penalty.note)
        self.assertIn('Product return penalty', penalty.note)
        self.assertIn('Cracked casing', penalty.note)
