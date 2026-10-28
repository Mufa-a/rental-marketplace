from django.urls import include, path

urlpatterns = [
    path("admin/", include("api.v1.admin_urls")),
    path("auth/", include("apps.accounts.urls")),
    path("properties/", include("apps.properties.urls")),
    path("viewings/", include("apps.viewings.urls")),
    path("payments/", include("apps.payments.urls")),
    path("referrals/", include("apps.referrals.urls")),
    path("trust/", include("apps.trust.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("verification/", include("apps.verification.urls")),
]
