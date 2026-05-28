# Generated manually for the LendR+ admin analytics dashboard.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Equipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('category', models.CharField(blank=True, max_length=80)),
                ('serial_number', models.CharField(blank=True, max_length=80, null=True, unique=True)),
                ('status', models.CharField(choices=[('available', 'Available'), ('borrowed', 'Borrowed'), ('maintenance', 'Under Maintenance'), ('retired', 'Retired')], default='available', max_length=20)),
                ('daily_penalty', models.DecimalField(decimal_places=2, default=2.0, max_digits=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Member',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('member_id', models.CharField(max_length=20, unique=True)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='member', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Borrow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('borrow_date', models.DateField()),
                ('due_date', models.DateField()),
                ('return_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('Active', 'Active'), ('Returned', 'Returned'), ('Overdue', 'Overdue'), ('Pending', 'Pending')], default='Active', max_length=20)),
                ('penalty', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('equipment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='borrowings', to='dashboard.equipment')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='borrowings', to='dashboard.member')),
            ],
        ),
    ]
