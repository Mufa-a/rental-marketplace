"""
Base Django settings — shared by dev.py and prod.py.
Values come from environment variables (see backend/.env.example).
"""
import os
from datetime import timedelta
from pathlib import Path

import environ

if os.name == "nt":
    OSGEO4W = r"C:\OSGeo4W"
    os.environ["OSGEO4W_ROOT"] = OSGEO4W
    os.environ["GDAL_DATA"] = OSGEO4W + r"\share\gdal"
    os.environ["PROJ_LIB"] = OSGEO4W + r"\share\proj"
    os.environ["PATH"] = OSGEO4W + r"\bin;" + os.environ["PATH"]
    GDAL_LIBRARY_PATH = OSGEO4W + r"\bin\gdal313.dll"
    GEOS_LIBRARY_PATH = OSGEO4W + r"\bin\geos_c.dll"
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY", default=env("SECRET_KEY", default=""))
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # Local apps
    "apps.accounts",
    "apps.properties",
    "apps.viewings",
    "apps.referrals",
    "apps.payments",
    "apps.verification",
    "apps.trust",
    "apps.notifications",
    "apps.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://rental:rental@localhost:5432/rental_marketplace")
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- DRF ----
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Tightened per-endpoint in Phase 2 (OTP) and Phase 5 (viewing requests).
        "otp_request": "3/15min",
        "login": "10/min",
        "viewing_request": "20/hour",
        "public_search": "120/min",
        "report": "10/hour",
        "deletion_request": "5/day",
    },
    # Set to the number of reverse proxies in front of Django (e.g. 1 behind
    # Caddy/nginx) so throttling keys on the real client IP. 0 = trust only
    # REMOTE_ADDR, which is the safe default when Django is exposed directly.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}

# ---- JWT ----
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# ---- CORS ----
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])

# ---- Cache / Celery (Redis) ----
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

# ---- Object storage (Cloudflare R2, S3-compatible) ----
STORAGES = {
    "default": {"BACKEND": "storages.backends.s3.S3Storage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
AWS_ACCESS_KEY_ID = env("R2_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("R2_BUCKET_NAME", default="")
AWS_S3_ENDPOINT_URL = env("R2_ENDPOINT_URL", default="")
AWS_S3_ADDRESSING_STYLE = "virtual"
R2_PUBLIC_BASE_URL = env("R2_PUBLIC_BASE_URL", default="").rstrip("/")

# ---- Third-party service credentials (used from Phase 2/5/6 onward) ----
AFRICASTALKING_USERNAME = env("AFRICASTALKING_USERNAME", default="")
AFRICASTALKING_API_KEY = env("AFRICASTALKING_API_KEY", default="")
MPESA_CONSUMER_KEY = env("MPESA_CONSUMER_KEY", default="")
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE = env("MPESA_SHORTCODE", default="")
MPESA_PASSKEY = env("MPESA_PASSKEY", default="")
MPESA_ENV = env("MPESA_ENV", default="sandbox")
MPESA_CALLBACK_URL = env("MPESA_CALLBACK_URL", default="")
MPESA_CALLBACK_TOKEN = env("MPESA_CALLBACK_TOKEN", default="")

SENTRY_DSN = env("SENTRY_DSN", default="")

# ---- Legal / consent ----
# Bump LEGAL_POLICY_VERSION whenever the Terms or Privacy Policy change in a
# way users should re-accept. It is stored with every ConsentRecord. Keep it in
# sync with frontend/lib/legal.ts (LEGAL_VERSION).
LEGAL_POLICY_VERSION = env("LEGAL_POLICY_VERSION", default="draft-1")

# ---- Admin URL ----
# Django admin path; override in production to something non-default.
ADMIN_URL = env("ADMIN_URL", default="admin/")
