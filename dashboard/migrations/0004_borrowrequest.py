import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_equipment_condition'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BorrowRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=150)),
                ('student_id', models.CharField(max_length=40)),
                ('phone_number', models.CharField(max_length=30)),
                ('purpose', models.TextField()),
                ('borrow_date', models.DateField()),
                ('duration_days', models.PositiveIntegerField()),
                ('expected_return_date', models.DateField()),
                ('status', models.CharField(choices=[('pending', 'Waiting for Approval'), ('approved', 'Approved'), ('denied', 'Request Denied'), ('return_pending', 'Return Pending'), ('returned', 'Returned')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('equipment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='borrow_requests', to='dashboard.equipment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='borrow_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'borrow_requests',
                'ordering': ['-created_at'],
            },
        ),
    ]
