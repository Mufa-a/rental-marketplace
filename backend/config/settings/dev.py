from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]
if not SECRET_KEY:
    SECRET_KEY = "local-development-only-insecure-key"

# Local HTTP: the refresh cookie cannot require HTTPS. Staff MFA is opt-in locally
# (STAFF_MFA_REQUIRED=True to try it; enrol with `python manage.py enroll_staff_totp`).
REFRESH_COOKIE = {**REFRESH_COOKIE, "secure": False}
STAFF_MFA_REQUIRED = env.bool("STAFF_MFA_REQUIRED", default=False)
