from .base import *  # noqa

if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS or ALLOWED_HOSTS == ["localhost", "127.0.0.1"]:
    raise RuntimeError("Set ALLOWED_HOSTS to explicit production hostnames.")
if not AFRICASTALKING_API_KEY or not AFRICASTALKING_USERNAME:
    raise RuntimeError("Africa's Talking credentials must be set in production to deliver OTPs.")

DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
