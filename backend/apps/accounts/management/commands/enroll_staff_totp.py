"""Enrol (or replace) an administrator's authenticator app. Requires server access by design.

    python manage.py enroll_staff_totp +254712345678
    python manage.py enroll_staff_totp +254712345678 --code 123456   # non-interactive confirmation

Add the printed secret (or otpauth link, e.g. as a QR code) to Google Authenticator, Microsoft
Authenticator, 1Password or similar, then enter the 6-digit code it shows to confirm.
"""
import pyotp
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.mfa import MFAError, encrypt_secret, verify
from apps.accounts.models import StaffTOTPDevice, User
from apps.accounts.serializers import normalize_phone
from apps.core.models import AuditLog
from apps.core.permissions import is_platform_admin


class Command(BaseCommand):
    help = "Enrol an administrator's authenticator app for the second sign-in step."

    def add_arguments(self, parser):
        parser.add_argument("phone_number")
        parser.add_argument("--code", help="Code from the app, to confirm without a prompt.")

    def handle(self, *args, phone_number, code=None, **options):
        user = User.objects.filter(phone_number=normalize_phone(phone_number)).first()
        if user is None or not is_platform_admin(user):
            raise CommandError("No active staff administrator with that phone number.")
        secret = pyotp.random_base32()
        device, _ = StaffTOTPDevice.objects.update_or_create(
            user=user, defaults={"secret_encrypted": encrypt_secret(secret), "confirmed_at": None, "last_used_step": 0})
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.phone_number, issuer_name="Nyumbani admin")
        self.stdout.write(f"Secret: {secret}\nLink (for a QR code): {uri}\nShow these only to the administrator, then clear your terminal.")
        code = code or input("6-digit code from the authenticator app: ")
        try:
            verify(device, code)
        except MFAError as exc:
            raise CommandError(f"{exc} The device was not confirmed; run the command again.")
        device.confirmed_at = timezone.now()
        device.save(update_fields=("confirmed_at",))
        AuditLog.objects.create(actor=None, action="auth.mfa_enrolled", object_type="accounts.User", object_id=str(user.pk))
        self.stdout.write(self.style.SUCCESS("Authenticator confirmed. This administrator now needs it at every sign-in."))
