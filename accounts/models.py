from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_USER = 'user'
    ROLE_ADMIN = 'admin'
    ROLE_CHOICES = [
        (ROLE_USER, 'User'),
        (ROLE_ADMIN, 'Administrator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER)
    department = models.CharField(max_length=120, blank=True)
    student_or_staff_id = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    reset_password_requested_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} profile"

# Create your models here.
