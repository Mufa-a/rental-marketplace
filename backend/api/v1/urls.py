from django.urls import include, path
from apps.core.admin_views import AdminOverviewView, AdminUserListView, AdminViewingRequestListView

urlpatterns = [
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),
    path("admin/users/", AdminUserListView.as_view(), name="admin-users"),
    path("admin/viewing-requests/", AdminViewingRequestListView.as_view(), name="admin-viewing-requests"),
    path("auth/", include("apps.accounts.urls")),
    path("properties/", include("apps.properties.urls")),
    path("viewings/", include("apps.viewings.urls")),
    path("payments/", include("apps.payments.urls")),
    path("referrals/", include("apps.referrals.urls")),
    path("trust/", include("apps.trust.urls")),
]
