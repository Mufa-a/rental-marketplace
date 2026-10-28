from django.urls import path

from apps.core import admin_api as a
from apps.core.admin_views import AdminOverviewView, AdminUserListView, AdminViewingRequestListView

urlpatterns = [
    path("overview/", AdminOverviewView.as_view(), name="admin-overview"),
    path("users/", AdminUserListView.as_view(), name="admin-users"),
    path("users/<int:user_id>/", a.AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("users/<int:user_id>/<str:action>/", a.AdminUserActionView.as_view(), name="admin-user-action"),
    path("viewing-requests/", AdminViewingRequestListView.as_view(), name="admin-viewing-requests"),
    path("listings/", a.AdminListingListView.as_view(), name="admin-listings"),
    path("listings/<int:unit_id>/moderate/", a.AdminListingModerateView.as_view(), name="admin-listing-moderate"),
    path("properties/", a.AdminPropertyListView.as_view(), name="admin-properties"),
    path("properties/<int:property_id>/verification/", a.PropertyVerificationDecisionView.as_view(), name="admin-property-verification"),
    path("landlord-verifications/", a.AdminVerificationListView.as_view(), name="admin-verifications"),
    path("landlord-verifications/<int:verification_id>/", a.AdminVerificationDetailView.as_view(), name="admin-verification-detail"),
    path("landlord-verifications/<int:verification_id>/decide/", a.AdminVerificationDecideView.as_view(), name="admin-verification-decide"),
    path("verification-documents/<int:document_id>/", a.AdminVerificationDocumentView.as_view(), name="admin-verification-document"),
    path("reports/", a.AdminReportListView.as_view(), name="admin-reports"),
    path("reports/<int:report_id>/resolve/", a.AdminReportResolveView.as_view(), name="admin-report-resolve"),
    path("referral-reviews/", a.AdminReferralReviewListView.as_view(), name="admin-referral-reviews"),
    path("viewings/<int:viewing_id>/ruling/", a.AdminViewingRulingView.as_view(), name="admin-viewing-ruling"),
    path("payments/", a.AdminPaymentListView.as_view(), name="admin-payments"),
    path("payments/<int:payment_id>/<str:action>/", a.AdminPaymentActionView.as_view(), name="admin-payment-action"),
    path("pricing/packages/", a.PackageListCreateView.as_view(), name="admin-packages"),
    path("pricing/packages/<int:pk>/", a.PackageDetailView.as_view(), name="admin-package-detail"),
    path("pricing/fee-rules/", a.FeeRuleListCreateView.as_view(), name="admin-fee-rules"),
    path("pricing/fee-rules/<int:pk>/", a.FeeRuleDetailView.as_view(), name="admin-fee-rule-detail"),
    path("pricing/service-prices/", a.ServicePriceListCreateView.as_view(), name="admin-service-prices"),
    path("pricing/service-prices/<int:pk>/", a.ServicePriceDetailView.as_view(), name="admin-service-price-detail"),
    path("audit-logs/", a.AdminAuditLogView.as_view(), name="admin-audit-logs"),
    path("audit-logs/verify/", a.AdminAuditVerifyView.as_view(), name="admin-audit-verify"),
    path("market/areas/", a.AdminAreaReportView.as_view(), name="admin-area-report"),
    path("market/trends/", a.AdminTrendView.as_view(), name="admin-trends"),
    path("exports/<str:name>.csv", a.AdminExportView.as_view(), name="admin-export"),
]
