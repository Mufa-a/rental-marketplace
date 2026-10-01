from .base import *  # noqa

if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS or ALLOWED_HOSTS == ["localhost", "127.0.0.1"]:
    raise RuntimeError("Set ALLOWED_HOSTS to explicit production hostnames.")
if not AFRICASTALKING_API_KEY or not AFRICASTALKING_USERNAME:
    raise RuntimeError("Africa's Talking credentials must be set in production to deliver OTPs.")

DEBUG = False

# ---- HTTPS / cookies / headers ----
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
# The health check must answer over plain HTTP from the container network.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
# Behind a TLS-terminating reverse proxy (Caddy/nginx/cloud LB) Django only sees HTTP;
# trust the proxy's forwarded-proto header so the redirect above does not loop.
if env.bool("BEHIND_TLS_PROXY", default=True):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ---- Static files (Django admin) served by WhiteNoise ----
STATIC_ROOT = BASE_DIR / "staticfiles"
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES["staticfiles"] = {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}

# ---- Database ----
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# ---- Logging: stdout only, no request bodies (which can contain OTP codes) ----
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
