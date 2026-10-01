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
    @pytest.mark.parametrize("path", ["/api/v1/admin/overview/", "/api/v1/admin/users/", "/api/v1/admin/viewing-requests/"])
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
