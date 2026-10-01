from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.core.health import healthz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include("api.v1.urls")),
]
