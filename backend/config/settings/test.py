"""
Test settings — isolates the test suite from live infrastructure (Redis,
S3/R2, real SMS) so `pytest` never depends on `docker compose up` having
been run first. CI and local `pytest` both use this.
"""
from .base import *  # noqa

DEBUG = True  # OTP delivery uses the local console adapter; never used by prod.
SECRET_KEY = "test-only-secret-key-not-for-deployment"
AFRICASTALKING_USERNAME = ""
AFRICASTALKING_API_KEY = ""

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# Celery tasks run synchronously in tests instead of needing a broker.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast, tests only
