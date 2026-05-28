from decimal import Decimal
from django.db import models


class EquipmentCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Equipment(models.Model):
    STATUS_AVAILABLE = 'available'
    STATUS_BORROWED = 'borrowed'
    STATUS_MAINTENANCE = 'maintenance'
    STATUS_RETIRED = 'retired'
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Available'),
        (STATUS_BORROWED, 'Borrowed'),
        (STATUS_MAINTENANCE, 'Maintenance'),
        (STATUS_RETIRED, 'Retired'),
    ]

    asset_tag = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=160)
    category = models.ForeignKey(EquipmentCategory, on_delete=models.PROTECT)
    lab_location = models.CharField(max_length=120)
    serial_number = models.CharField(max_length=120, blank=True)
    condition = models.CharField(max_length=120, default='Good')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    daily_penalty_rate = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('5.00'))
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.asset_tag} - {self.name}"

# Create your models here.
