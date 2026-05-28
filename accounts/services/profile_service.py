from django.contrib.auth.models import Group
from accounts.models import UserProfile


class ProfileService:
    def get_or_create_profile(self, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if user.is_staff and profile.role != UserProfile.ROLE_ADMIN:
            profile.role = UserProfile.ROLE_ADMIN
            profile.save(update_fields=['role'])
        return profile

    def update_profile(self, user, department, student_or_staff_id, phone_number):
        profile = self.get_or_create_profile(user)
        profile.department = department
        profile.student_or_staff_id = student_or_staff_id
        profile.phone_number = phone_number
        profile.save()
        return profile

    def is_admin(self, user):
        if not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        profile = self.get_or_create_profile(user)
        return profile.role == UserProfile.ROLE_ADMIN or user.groups.filter(name='Admin').exists()

    def ensure_default_groups(self):
        Group.objects.get_or_create(name='Admin')
        Group.objects.get_or_create(name='User')
