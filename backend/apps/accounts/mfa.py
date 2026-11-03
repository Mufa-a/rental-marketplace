"""Second factor (TOTP authenticator app) for platform administrators.

Admins sign in with the phone OTP as everyone else, then must enter a code from an authenticator
app. This closes the SIM-swap path to the admin console. Devices are enrolled by an operator with
server access (`python manage.py enroll_staff_totp <phone>`), never through the website, so a
hijacked phone number cannot enrol a new device. Secrets are encrypted at rest.
"""
import base64
import hashlib
import time

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.utils import timezone

TICKET_SALT = "nyumbani.mfa-ticket"
TICKET_MAX_AGE = 300
MAX_ATTEMPTS = 5


class MFAError(Exception):
    pass


def _fernet():
    key = settings.TOTP_ENCRYPTION_KEY or base64.urlsafe_b64encode(hashlib.sha256(f"{settings.SECRET_KEY}:totp".encode()).digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(secret):
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise MFAError("This authenticator could not be read. Re-enrol it.") from exc


def mfa_required_for(user):
    from apps.core.permissions import is_platform_admin
    return settings.STAFF_MFA_REQUIRED and is_platform_admin(user)


def issue_ticket(user):
    return signing.dumps({"uid": user.pk}, salt=TICKET_SALT, compress=True)


def user_id_from_ticket(ticket):
    try:
        return signing.loads(ticket, salt=TICKET_SALT, max_age=TICKET_MAX_AGE)["uid"]
    except (signing.BadSignature, KeyError, TypeError) as exc:
        raise MFAError("Your sign-in step expired. Start again with a new SMS code.") from exc


def verify(device, code):
    """Check a 6-digit code, allowing one 30-second step of clock drift, and refuse replays."""
    attempts_key = f"mfa-attempts:{device.user_id}"
    attempts = cache.get(attempts_key, 0)
    if attempts >= MAX_ATTEMPTS:
        raise MFAError("Too many attempts. Wait 15 minutes and sign in again.")
    totp = pyotp.TOTP(decrypt_secret(device.secret_encrypted))
    now_step = int(time.time()) // totp.interval
    matched_step = next((step for step in (now_step - 1, now_step, now_step + 1)
                         if totp.at(step * totp.interval) == str(code).strip()), None)
    if matched_step is None or matched_step <= device.last_used_step:
        cache.set(attempts_key, attempts + 1, timeout=900)
        raise MFAError("That authenticator code is not valid.")
    cache.delete(attempts_key)
    device.last_used_step = matched_step
    device.last_used_at = timezone.now()
    device.save(update_fields=("last_used_step", "last_used_at"))
    return True
