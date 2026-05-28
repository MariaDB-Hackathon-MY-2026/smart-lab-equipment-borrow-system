from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send a test email through the configured Django email backend."

    def add_arguments(self, parser):
        parser.add_argument("recipient", help="Email address that should receive the test message.")

    def handle(self, *args, **options):
        recipient = options["recipient"]
        if settings.EMAIL_BACKEND.endswith("smtp.EmailBackend") and not settings.EMAIL_HOST_PASSWORD:
            raise CommandError("SMTP email is enabled, but EMAIL_HOST_PASSWORD or BREVO_SMTP_KEY is missing.")

        sent_count = send_mail(
            "lendr+ email test",
            "This is a test email from lendr+. If you received this, Brevo SMTP is configured correctly.",
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )

        if sent_count:
            self.stdout.write(self.style.SUCCESS(f"Test email sent to {recipient}."))
        else:
            raise CommandError("Django did not report a sent email.")
