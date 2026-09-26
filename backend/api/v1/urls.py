from django.urls import include, path
from apps.core.admin_views import AdminOverviewView

urlpatterns = [
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),
    path("auth/", include("apps.accounts.urls")),
    path("properties/", include("apps.properties.urls")),
    path("viewings/", include("apps.viewings.urls")),
    path("payments/", include("apps.payments.urls")),
    path("referrals/", include("apps.referrals.urls")),
]
