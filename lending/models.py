import os
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from equipment.models import Equipment


def return_photo_upload_path(instance, filename):
    # Kept for historical migration 0003; the return-photo feature has been removed.
    _, extension = os.path.splitext(filename)
    safe_extension = extension.lower() or '.jpg'
    return f'return-photos/request-{instance.lending_request_id}/{instance.side}{safe_extension}'


class LendingRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_DENIED = 'denied'
    STATUS_BORROWED = 'borrowed'
    STATUS_RETURN_REQUESTED = 'return_requested'
    STATUS_RETURNED = 'returned'
    STATUS_OVERDUE = 'overdue'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_DENIED, 'Denied'),
        (STATUS_BORROWED, 'Borrowed'),
        (STATUS_RETURN_REQUESTED, 'Return Requested'),
        (STATUS_RETURNED, 'Returned'),
        (STATUS_OVERDUE, 'Overdue'),
    ]

    borrower = models.ForeignKey(User, on_delete=models.CASCADE)
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT)
    purpose = models.TextField()
    requested_from = models.DateField()
    requested_until = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_note = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_lending_requests')
    approved_at = models.DateTimeField(null=True, blank=True)
    borrowed_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.borrower.username} - {self.equipment.name} ({self.status})"


class Penalty(models.Model):
    STATUS_UNPAID = 'unpaid'
    STATUS_PAID = 'paid'
    STATUS_WAIVED = 'waived'
    STATUS_CHOICES = [
        (STATUS_UNPAID, 'Unpaid'),
        (STATUS_PAID, 'Paid'),
        (STATUS_WAIVED, 'Waived'),
    ]

    lending_request = models.OneToOneField(LendingRequest, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    product_penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    days_overdue = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNPAID)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Penalty RM {self.amount} for request #{self.lending_request_id}"

# Create your models here.
