"""
OTP generation, delivery, and verification — the logic behind the
otp/request and otp/verify endpoints.

In dev (no AFRICASTALKING_API_KEY configured) the code is logged instead
of sent, so the whole flow is testable without real SMS costs or
credentials. Swap in the WhatsApp Business API here later as a cheaper
fallback per the documentation, without touching the view layer.
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from .models import OTPCode, User

OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class OTPLocked(Exception):
    """Too many failed attempts — phone is temporarily locked."""


class OTPInvalid(Exception):
    """Code is wrong, expired, already used, or none was requested."""


def generate_otp_code() -> str:
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def send_otp(user: User) -> OTPCode:
    active_lock = (
        OTPCode.objects.filter(user=user, locked_until__gt=timezone.now())
        .order_by("-locked_until")
        .first()
    )
    if active_lock:
        raise OTPLocked(f"Too many attempts. Try again after {active_lock.locked_until.isoformat()}.")

    # Only the latest code is valid. Mark older codes used before sending a
    # replacement so a delayed SMS cannot remain a second active credential.
    OTPCode.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
    code = generate_otp_code()
    otp = OTPCode.objects.create(
        user=user,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    _deliver(user.phone_number, code)
    return otp


def _deliver(phone_number: str, code: str) -> None:
    if not settings.AFRICASTALKING_API_KEY:
        if settings.DEBUG:
            # Local development only. Never log authentication secrets from
            # staging or production when the SMS provider is misconfigured.
            print(f"\n[DEV OTP] {phone_number}: {code} (expires in {OTP_TTL_MINUTES} minutes)\n", flush=True)
            return
        raise RuntimeError("SMS delivery is not configured.")

    import africastalking

    africastalking.initialize(settings.AFRICASTALKING_USERNAME, settings.AFRICASTALKING_API_KEY)
    africastalking.SMS.send(
        f"Your verification code is {code}. It expires in {OTP_TTL_MINUTES} minutes.",
        [phone_number],
    )


def verify_otp(user: User, submitted_code: str) -> None:
    otp = (
        OTPCode.objects.filter(user=user, used_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        raise OTPInvalid("No pending code for this number. Request a new one.")

    if otp.locked_until and timezone.now() < otp.locked_until:
        raise OTPLocked(f"Too many attempts. Try again after {otp.locked_until.isoformat()}.")

    if timezone.now() > otp.expires_at:
        raise OTPInvalid("Code has expired. Request a new one.")

    if not check_password(submitted_code, otp.code_hash):
        otp.failed_attempts += 1
        if otp.failed_attempts >= MAX_FAILED_ATTEMPTS:
            otp.locked_until = timezone.now() + timedelta(minutes=LOCKOUT_MINUTES)
        otp.save(update_fields=["failed_attempts", "locked_until"])
        raise OTPInvalid("Incorrect code.")

    otp.used_at = timezone.now()
    otp.save(update_fields=["used_at"])
    user.phone_verified = True
    user.is_active = True
    user.save(update_fields=["phone_verified", "is_active"])
