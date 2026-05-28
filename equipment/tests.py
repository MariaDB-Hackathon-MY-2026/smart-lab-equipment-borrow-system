from unittest.mock import Mock
from django.test import SimpleTestCase

from equipment.models import Equipment
from equipment.services.equipment_service import EquipmentService


class EquipmentDeletionTests(SimpleTestCase):
    def test_soft_delete_rejects_borrowed_equipment(self):
        equipment = Mock(status=Equipment.STATUS_BORROWED)
        service = EquipmentService()
        service.get_equipment = Mock(return_value=equipment)

        with self.assertRaisesMessage(ValueError, 'Borrowed equipment cannot be deleted until it is returned.'):
            service.soft_delete_equipment(1)

        equipment.save.assert_not_called()

    def test_soft_delete_allows_non_borrowed_equipment(self):
        equipment = Mock(status=Equipment.STATUS_AVAILABLE, is_active=True)
        service = EquipmentService()
        service.get_equipment = Mock(return_value=equipment)

        result = service.soft_delete_equipment(1)

        self.assertIs(result, equipment)
        self.assertFalse(equipment.is_active)
        equipment.save.assert_called_once_with(update_fields=['is_active'])
