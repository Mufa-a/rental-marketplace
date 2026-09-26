from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]
if not SECRET_KEY:
    SECRET_KEY = "local-development-only-insecure-key"
