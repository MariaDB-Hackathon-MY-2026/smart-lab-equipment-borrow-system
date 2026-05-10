from decimal import Decimal, InvalidOperation
from equipment.models import Equipment, EquipmentCategory


class EquipmentService:
    DEFAULT_CATEGORY_NAMES = [
        'Audio Visual',
        'Computing',
        'Electronics',
        'Lab Instruments',
        'Measurement Tools',
        'Networking',
        'Safety Equipment',
    ]
    CONDITION_CHOICES = [
        'Excellent',
        'Good',
        'Fair',
        'Needs Inspection',
        'Damaged',
    ]
    CATEGORY_ICON_RULES = [
        (('vr', 'virtual reality', 'headset'), 'fa-solid fa-vr-cardboard'),
        (('camera', 'photo', 'imaging', 'optics', 'lens'), 'fa-solid fa-camera'),
        (('drone', 'uav', 'quadcopter'), 'fa-solid fa-helicopter'),
        (('hdd', 'hard drive', 'drive', 'storage', 'ssd', 'disk'), 'fa-solid fa-hard-drive'),
        (('laptop', 'computer', 'computing', 'tablet', 'pc'), 'fa-solid fa-laptop'),
        (('meter', 'measurement', 'calibration', 'probe', 'sensor'), 'fa-solid fa-gauge-high'),
        (('audio', 'speaker', 'microphone'), 'fa-solid fa-volume-high'),
        (('visual', 'projector', 'display', 'monitor', 'screen'), 'fa-solid fa-display'),
        (('network', 'router', 'switch', 'wifi'), 'fa-solid fa-network-wired'),
        (('safety', 'ppe', 'protective', 'helmet'), 'fa-solid fa-shield-halved'),
        (('microscope', 'lab', 'instrument', 'science'), 'fa-solid fa-flask'),
        (('battery', 'power', 'charger'), 'fa-solid fa-battery-full'),
        (('cable', 'adapter', 'connector'), 'fa-solid fa-plug'),
        (('robot', 'robotics'), 'fa-solid fa-robot'),
    ]

    def list_active_equipment(self):
        return Equipment.objects.select_related('category').filter(is_active=True).order_by('name')

    def category_icon_class(self, category_name):
        normalized_name = category_name.lower()
        for keywords, icon_class in self.CATEGORY_ICON_RULES:
            if any(keyword in normalized_name for keyword in keywords):
                return icon_class
        return 'fa-solid fa-cube'

    def attach_category_icons(self, equipments):
        for equipment in equipments:
            equipment.category_icon_class = self.category_icon_class(equipment.category.name)
        return equipments

    def list_available_equipment(self):
        return self.list_active_equipment().filter(status=Equipment.STATUS_AVAILABLE)

    def get_equipment(self, equipment_id):
        return Equipment.objects.select_related('category').get(id=equipment_id, is_active=True)

    def list_categories(self):
        return EquipmentCategory.objects.filter(is_active=True).order_by('name')

    def list_category_options(self):
        return list(self.list_categories().values_list('name', flat=True))

    def create_category_if_missing(self, name):
        category, _ = EquipmentCategory.objects.get_or_create(name=name.strip())
        if not category.is_active:
            category.is_active = True
            category.save(update_fields=['is_active'])
        return category

    def create_category(self, name, description=''):
        name = name.strip()
        if not name:
            raise ValueError('Category name is required.')

        existing = EquipmentCategory.objects.filter(name__iexact=name).first()
        if existing:
            if existing.is_active:
                raise ValueError('This category already exists.')
            existing.name = name
            existing.description = description.strip()
            existing.is_active = True
            existing.save(update_fields=['name', 'description', 'is_active'])
            return existing

        return EquipmentCategory.objects.create(name=name, description=description.strip())

    def update_category(self, category_id, name, description=''):
        name = name.strip()
        if not name:
            raise ValueError('Category name is required.')

        try:
            category = EquipmentCategory.objects.get(id=category_id, is_active=True)
        except EquipmentCategory.DoesNotExist:
            raise ValueError('Category not found.')
        duplicate = EquipmentCategory.objects.filter(name__iexact=name, is_active=True).exclude(id=category_id).exists()
        if duplicate:
            raise ValueError('Another active category already uses this name.')

        category.name = name
        category.description = description.strip()
        category.save(update_fields=['name', 'description'])
        return category

    def soft_delete_category(self, category_id):
        try:
            category = EquipmentCategory.objects.get(id=category_id, is_active=True)
        except EquipmentCategory.DoesNotExist:
            raise ValueError('Category not found.')
        category.is_active = False
        category.save(update_fields=['is_active'])
        return category

    def clean_equipment_data(self, data):
        required_fields = {
            'asset_tag': 'Asset Tag',
            'name': 'Equipment Name',
            'category': 'Category',
            'lab_location': 'Lab Location',
            'serial_number': 'Serial Number',
            'condition': 'Condition',
            'status': 'Status',
        }
        cleaned = {}
        for field, label in required_fields.items():
            value = data.get(field, '').strip()
            if not value:
                raise ValueError(f'{label} is required.')
            cleaned[field] = value

        if cleaned['condition'] not in self.CONDITION_CHOICES:
            raise ValueError('Please select a valid condition.')

        valid_statuses = [status for status, _ in Equipment.STATUS_CHOICES]
        if cleaned['status'] not in valid_statuses:
            raise ValueError('Please select a valid status.')

        try:
            daily_penalty_rate = Decimal(data.get('daily_penalty_rate') or '0.00')
        except (InvalidOperation, TypeError):
            raise ValueError('Daily Penalty Rate must be a valid MYR amount.')

        if daily_penalty_rate < Decimal('0.00'):
            raise ValueError('Daily Penalty Rate cannot be negative.')

        cleaned['daily_penalty_rate'] = daily_penalty_rate
        cleaned['notes'] = data.get('notes', '').strip()
        return cleaned

    def create_equipment(self, data):
        cleaned = self.clean_equipment_data(data)
        category = self.create_category_if_missing(cleaned['category'])
        return Equipment.objects.create(
            asset_tag=cleaned['asset_tag'],
            name=cleaned['name'],
            category=category,
            lab_location=cleaned['lab_location'],
            serial_number=cleaned['serial_number'],
            condition=cleaned['condition'],
            status=cleaned['status'],
            daily_penalty_rate=cleaned['daily_penalty_rate'],
            notes=cleaned['notes'],
        )

    def update_equipment(self, equipment_id, data):
        equipment = self.get_equipment(equipment_id)
        cleaned = self.clean_equipment_data(data)
        equipment.asset_tag = cleaned['asset_tag']
        equipment.name = cleaned['name']
        equipment.category = self.create_category_if_missing(cleaned['category'])
        equipment.lab_location = cleaned['lab_location']
        equipment.serial_number = cleaned['serial_number']
        equipment.condition = cleaned['condition']
        equipment.status = cleaned['status']
        equipment.daily_penalty_rate = cleaned['daily_penalty_rate']
        equipment.notes = cleaned['notes']
        equipment.save()
        return equipment

    def soft_delete_equipment(self, equipment_id):
        equipment = self.get_equipment(equipment_id)
        if equipment.status == Equipment.STATUS_BORROWED:
            raise ValueError('Borrowed equipment cannot be deleted until it is returned.')
        equipment.is_active = False
        equipment.save(update_fields=['is_active'])
        return equipment
