import random
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from dashboard.models import Borrow, Equipment, Member


EQUIPMENT_NAMES = [
    ('DSLR Canon EOS R', 'Camera'),
    ('Projector Epson X5', 'AV'),
    ('DJI Mini 4 Pro', 'Drone'),
    ('Godox Lighting Kit', 'Lighting'),
    ('Manfrotto Tripod 190', 'Accessory'),
    ('Sony A7 IV', 'Camera'),
    ('GoPro Hero 12', 'Camera'),
    ('Roland Audio Interface', 'Audio'),
    ('LED Panel 200W', 'Lighting'),
    ('Sennheiser Shotgun Mic', 'Audio'),
]

MEMBERS = [
    ('ahmad', 'Ahmad', 'Farid', 'ahmad.farid@email.com'),
    ('siti', 'Siti', 'Nabilah', 'siti.nabilah@email.com'),
    ('ravi', 'Ravi', 'Kumar', 'ravi.kumar@email.com'),
    ('nurul', 'Nurul', 'Ain', 'nurul.ain@email.com'),
    ('hazwan', 'Hazwan', 'Yusof', 'hazwan.yusof@email.com'),
    ('lim', 'Lim', 'Wei Jie', 'lim.weijie@email.com'),
]


class Command(BaseCommand):
    help = 'Seed LendR+ with sample equipment, members, and borrowing records.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding LendR+ data...')

        equipment_objects = []
        for i, (name, category) in enumerate(EQUIPMENT_NAMES):
            equipment, _ = Equipment.objects.get_or_create(
                name=name,
                defaults={
                    'category': category,
                    'serial_number': f'SN-{1000 + i}',
                    'daily_penalty': 2.00,
                },
            )
            equipment_objects.append(equipment)

        member_objects = []
        for index, (username, first_name, last_name, email) in enumerate(MEMBERS):
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                },
            )
            member, _ = Member.objects.get_or_create(
                user=user,
                defaults={'member_id': f'M-{1000 + index:04d}'},
            )
            member_objects.append(member)

        today = date.today()
        statuses = ['Active', 'Returned', 'Overdue', 'Pending']
        weights = [0.4, 0.35, 0.15, 0.10]

        for _ in range(30):
            member = random.choice(member_objects)
            equipment = random.choice(equipment_objects)
            borrow_date = today - timedelta(days=random.randint(2, 30))
            due_date = borrow_date + timedelta(days=random.randint(3, 10))
            status = random.choices(statuses, weights=weights)[0]
            penalty = None

            if status == 'Overdue':
                overdue_days = (today - due_date).days
                penalty = max(0, overdue_days) * float(equipment.daily_penalty)

            Borrow.objects.create(
                member=member,
                equipment=equipment,
                borrow_date=borrow_date,
                due_date=due_date,
                return_date=today if status == 'Returned' else None,
                status=status,
                penalty=penalty,
            )

        self.stdout.write(self.style.SUCCESS('Seed complete!'))
