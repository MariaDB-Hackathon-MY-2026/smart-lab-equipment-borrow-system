from django.contrib.auth.tokens import PasswordResetTokenGenerator

from accounts.models import UserProfile


class LatestPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        requested_at = profile.reset_password_requested_at
        requested_at_value = str(int(requested_at.timestamp())) if requested_at else ""

        return (
            f"{user.pk}{user.password}{user.last_login}{timestamp}"
            f"{requested_at_value}{user.email}"
        )


latest_password_reset_token_generator = LatestPasswordResetTokenGenerator()
