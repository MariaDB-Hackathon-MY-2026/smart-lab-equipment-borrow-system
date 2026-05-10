from django.core.management.base import BaseCommand
from accounts.services.profile_service import ProfileService
from equipment.models import Equipment, EquipmentCategory


class Command(BaseCommand):
    help = 'Seed default Lendr groups, categories, and sample lab equipment.'

    def handle(self, *args, **options):
        ProfileService().ensure_default_groups()

        categories = {
            'Measurement': 'Meters, probes, and calibration devices.',
            'Optics': 'Lab optics and imaging equipment.',
            'Computing': 'Portable computing and embedded devices.',
        }

        category_objects = {}
        for name, description in categories.items():
            category, _ = EquipmentCategory.objects.update_or_create(
                name=name,
                defaults={'description': description, 'is_active': True},
            )
            category_objects[name] = category

        samples = [
            {
                'asset_tag': 'LAB-MEAS-001',
                'name': 'Digital Oscilloscope',
                'category': category_objects['Measurement'],
                'lab_location': 'Engineering Lab A',
                'serial_number': 'OSC-2026-001',
                'condition': 'Good',
                'daily_penalty_rate': 10.00,
            },
            {
                'asset_tag': 'LAB-OPT-002',
                'name': 'Stereo Microscope',
                'category': category_objects['Optics'],
                'lab_location': 'Biology Lab B',
                'serial_number': 'MIC-2026-002',
                'condition': 'Excellent',
                'daily_penalty_rate': 8.00,
            },
            {
                'asset_tag': 'LAB-COMP-003',
                'name': 'Raspberry Pi Lab Kit',
                'category': category_objects['Computing'],
                'lab_location': 'IoT Lab C',
                'serial_number': 'RPI-2026-003',
                'condition': 'Good',
                'daily_penalty_rate': 5.00,
            },
        ]

        for sample in samples:
            Equipment.objects.update_or_create(
                asset_tag=sample['asset_tag'],
                defaults={**sample, 'status': Equipment.STATUS_AVAILABLE, 'is_active': True},
            )

        self.stdout.write(self.style.SUCCESS('Lendr seed data created.'))
