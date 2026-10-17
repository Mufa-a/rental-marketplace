import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.admin_views import mask_phone
from apps.core.models import AuditLog


def _admin():
    return User.objects.create_superuser(phone_number="+254700000061", password="secure-test-password")


def test_mask_phone_hides_the_middle_digits():
    assert mask_phone("+254712345678") == "+2547••••••78"
    assert mask_phone("") == "•••"


@pytest.mark.django_db
class TestAdminAccess:
    @pytest.mark.parametrize("path", [
        "/api/v1/admin/overview/", "/api/v1/admin/users/", "/api/v1/admin/viewing-requests/",
        "/api/v1/admin/reports/", "/api/v1/admin/properties/",
    ])
    def test_only_admins_can_use_admin_endpoints(self, path):
        assert APIClient().get(path).status_code == 401
        for number, role in (("+254700000071", "tenant"), ("+254700000072", "landlord")):
            user = User.objects.create_user(username=role, phone_number=number, role=role)
            client = APIClient()
            client.force_authenticate(user)
            assert client.get(path).status_code == 403

    def test_overview_masks_phone_numbers_and_logs_the_access(self):
        admin = _admin()
        User.objects.create_user(username="ten", phone_number="+254712345678", role="tenant")
        client = APIClient()
        client.force_authenticate(admin)
        response = client.get("/api/v1/admin/overview/")
        assert response.status_code == 200
        assert "+254712345678" not in response.content.decode()
        assert response.data["user_totals"]["tenants"] == 1
        assert any(user["phone"] == "+2547••••••78" for user in response.data["recent_users"])
        assert AuditLog.objects.filter(actor=admin, action="admin.overview_viewed").exists()

    def test_user_list_supports_search_filter_and_pagination_and_is_audited(self):
        admin = _admin()
        for index in range(25):
            User.objects.create_user(username=f"t{index}", phone_number=f"+2547000001{index:02d}", role="tenant")
        User.objects.create_user(username="ll", phone_number="+254700000199", role="landlord")
        client = APIClient()
        client.force_authenticate(admin)
        page = client.get("/api/v1/admin/users/?role=tenant")
        assert page.data["count"] == 25 and len(page.data["results"]) == 20 and page.data["next"]
        assert client.get("/api/v1/admin/users/?role=landlord").data["count"] == 1
        assert client.get("/api/v1/admin/users/?search=99").data["count"] == 1
        assert client.get("/api/v1/admin/users/?ordering=--drop").status_code == 200  # unknown ordering falls back safely
        assert AuditLog.objects.filter(action="admin.users_listed").exists()


@pytest.mark.django_db
def test_health_check_needs_no_auth_and_leaks_nothing(client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _listing(suffix="1"):
    from apps.accounts.models import LandlordProfile
    from apps.properties.models import Property, Unit

    owner = User.objects.create_user(username=f"owner{suffix}", phone_number=f"+25472200{suffix}0", role="landlord")
    prop = Property.objects.create(landlord=LandlordProfile.objects.create(user=owner), name=f"Prop {suffix}", address_line="1", area="Kilimani", city="Nairobi", county="Nairobi")
    return owner, prop, Unit.objects.create(property=prop, unit_number="1", title=f"Unit {suffix}", unit_type="studio", monthly_rent=10000, is_published=True)


@pytest.mark.django_db
class TestAdminReportsAndVerificationQueues:
    def _client(self):
        client = APIClient()
        client.force_authenticate(_admin())
        return client

    def test_reports_queue_masks_identities_and_shows_open_count_per_listing(self):
        from apps.trust.models import Report

        owner, _, unit = _listing()
        for n in range(2):
            reporter = User.objects.create_user(username=f"rp{n}", phone_number=f"+25471299990{n}", role="tenant")
            Report.objects.create(reporter=reporter, reported_user=owner, listing=unit, reason="fraudulent_listing", detail="asked for a deposit")
        response = self._client().get("/api/v1/admin/reports/")
        assert response.status_code == 200 and response.data["count"] == 2
        body = response.content.decode()
        assert "+254712999900" not in body and owner.phone_number not in body
        row = response.data["results"][0]
        assert row["listing"] == "Unit 1" and row["open_reports_on_listing"] == 2 and row["reason"] == "fraudulent_listing"
        assert row["reporter"].startswith("+2547") and "•" in row["reporter"]

    def test_state_filter_separates_open_from_resolved(self):
        from django.utils import timezone
        from apps.trust.models import Report

        owner, _, unit = _listing()
        admin = User.objects.create_user(username="a2", phone_number="+254700000198", role="admin")
        reporter = User.objects.create_user(username="rp", phone_number="+254712999911", role="tenant")
        Report.objects.create(reporter=reporter, reported_user=owner, listing=unit, reason="other", resolved_at=timezone.now(), resolution="dismissed", resolved_by=admin)
        client = self._client()
        assert client.get("/api/v1/admin/reports/").data["count"] == 0
        assert client.get("/api/v1/admin/reports/?state=resolved").data["count"] == 1
        assert client.get("/api/v1/admin/reports/?state=all").data["count"] == 1

    def test_reports_listing_is_audited(self):
        self._client().get("/api/v1/admin/reports/")
        assert AuditLog.objects.filter(action="admin.reports_listed").exists()

    def test_verification_queue_lists_pending_properties_oldest_first_with_payment_flag(self):
        from apps.payments.models import Payment
        from apps.properties.models import Property

        _, paid, _ = _listing("1")
        _, unpaid, _ = _listing("2")
        _, other, _ = _listing("3")
        Property.objects.filter(pk__in=[paid.pk, unpaid.pk]).update(verification_status="pending")
        Payment.objects.create(
            purpose="verification_fee", property=paid, amount=2000, phone_number="+254722000010", provider_reference="r1",
            idempotency_key="k1", status="successful",
        )
        response = self._client().get("/api/v1/admin/properties/")
        assert response.data["count"] == 2
        names = [row["name"] for row in response.data["results"]]
        assert names == ["Prop 1", "Prop 2"] and other.name not in names
        flags = {row["name"]: row["verification_fee_paid"] for row in response.data["results"]}
        assert flags == {"Prop 1": True, "Prop 2": False}
        assert "+25472200" not in response.content.decode()

    def test_verification_queue_status_filter(self):
        from apps.properties.models import Property

        _, prop, _ = _listing()
        Property.objects.filter(pk=prop.pk).update(verification_status="rejected")
        client = self._client()
        assert client.get("/api/v1/admin/properties/").data["count"] == 0
        assert client.get("/api/v1/admin/properties/?status=rejected").data["count"] == 1
        assert client.get("/api/v1/admin/properties/?status=all").data["count"] == 1
