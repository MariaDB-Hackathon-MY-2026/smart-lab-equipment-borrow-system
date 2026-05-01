from django.contrib.auth.models import User
from django.db import models

from .db_services import calculate_penalty_in_db


class Member(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='member')
    member_id = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_full_name(self):
        return self.user.get_full_name()

    @property
    def first_name(self):
        return self.user.first_name

    def __str__(self):
        return f"{self.member_id} - {self.get_full_name()}"


class Equipment(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('borrowed', 'Borrowed'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
    ]
    CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('damaged', 'Damaged'),
        ('needs_repair', 'Needs Repair'),
    ]

    name = models.CharField(max_length=150)
    category = models.CharField(max_length=80, blank=True)
    serial_number = models.CharField(max_length=80, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    condition_remarks = models.TextField(blank=True)
    daily_penalty = models.DecimalField(max_digits=8, decimal_places=2, default=2.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Borrow(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Returned', 'Returned'),
        ('Overdue', 'Overdue'),
        ('Pending', 'Pending'),
        ('Rejected', 'Rejected'),
    ]

    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name='borrowings')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='borrowings')
    borrow_date = models.DateField()
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    penalty = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def calculate_penalty(self):
        from django.utils import timezone

        db_penalty = calculate_penalty_in_db(self.id, timezone.now().date()) if self.pk else None
        if db_penalty is not None:
            return db_penalty

        if self.status == 'Overdue' and not self.return_date:
            overdue_days = (timezone.now().date() - self.due_date).days
            return max(0, overdue_days) * self.equipment.daily_penalty
        return None

    def __str__(self):
        return f"{self.member} -> {self.equipment} ({self.status})"


class BorrowRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Waiting for Approval'),
        ('approved', 'Approved'),
        ('denied', 'Request Denied'),
        ('return_pending', 'Return Pending'),
        ('returned', 'Returned'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='borrow_requests')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='borrow_requests')
    full_name = models.CharField(max_length=150)
    student_id = models.CharField(max_length=40)
    faculty_department = models.CharField(max_length=120, blank=True)
    email = models.EmailField(max_length=254)
    phone_number = models.CharField(max_length=30)
    purpose = models.TextField()
    borrow_date = models.DateField()
    duration_days = models.PositiveIntegerField()
    expected_return_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'borrow_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_username()} -> {self.equipment.name} ({self.status})"
