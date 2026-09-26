"""
Covers the OTP auth path end to end — this is a revenue/security-integrity
path (it gates every other feature), so it's tested from Phase 2 onward
rather than deferred.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import OTPCode, User


@pytest.fixture(autouse=True)
def keep_sms_out_of_tests(monkeypatch):
    monkeypatch.setattr("apps.accounts.services._deliver", lambda phone, code: None)


@pytest.mark.django_db
class TestOTPFlow:
    def test_request_otp_creates_inactive_user_and_code(self):
        client = APIClient()
        response = client.post(
            "/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant"}
        )
        assert response.status_code == 200
        user = User.objects.get(phone_number="+254712345678")
        assert user.is_active is False
        assert OTPCode.objects.filter(user=user).exists()

    def test_wrong_code_is_rejected_and_counted(self):
        client = APIClient()
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant"})
        response = client.post(
            "/api/v1/auth/otp/verify/", {"phone_number": "0712345678", "code": "000000"}
        )
        assert response.status_code == 400
        otp = OTPCode.objects.latest("created_at")
        assert otp.failed_attempts == 1

    def test_five_wrong_codes_locks_out_further_attempts(self):
        client = APIClient()
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant"})
        for _ in range(5):
            client.post("/api/v1/auth/otp/verify/", {"phone_number": "0712345678", "code": "000000"})
        response = client.post(
            "/api/v1/auth/otp/verify/", {"phone_number": "0712345678", "code": "000000"}
        )
        assert response.status_code == 429

    def test_correct_code_activates_user_and_returns_tokens(self, monkeypatch):
        import apps.accounts.services as services

        monkeypatch.setattr(services, "generate_otp_code", lambda: "111111")

        client = APIClient()
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant"})
        response = client.post(
            "/api/v1/auth/otp/verify/", {"phone_number": "0712345678", "code": "111111"}
        )
        assert response.status_code == 200
        assert "access" in response.data
        user = User.objects.get(phone_number="+254712345678")
        assert user.is_active is True
        assert user.phone_verified is True

    def test_me_endpoint_requires_valid_token(self):
        client = APIClient()
        response = client.get("/api/v1/auth/me/")
        assert response.status_code == 401

    def test_public_registration_cannot_assign_admin_role(self):
        client = APIClient()
        response = client.post(
            "/api/v1/auth/otp/request/",
            {"phone_number": "0712345678", "role": "admin"},
            format="json",
        )
        assert response.status_code == 400
        assert not User.objects.filter(phone_number="+254712345678").exists()

    def test_profile_can_be_read_and_updated_with_authentication(self):
        user = User.objects.create_user(
            username="0712345678", phone_number="+254712345678", role="tenant"
        )
        client = APIClient()
        client.force_authenticate(user)
        response = client.patch("/api/v1/auth/me/", {"first_name": "Amina", "role": "admin"}, format="json")
        assert response.status_code == 200
        assert response.data["first_name"] == "Amina"
        assert response.data["role"] == "tenant"

    def test_resending_code_invalidates_previous_code(self, monkeypatch):
        import apps.accounts.services as services

        codes = iter(("111111", "222222"))
        monkeypatch.setattr(services, "generate_otp_code", lambda: next(codes))
        client = APIClient()
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant"})
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678"})
        old_code = client.post("/api/v1/auth/otp/verify/", {"phone_number": "0712345678", "code": "111111"})
        current_code = client.post("/api/v1/auth/otp/verify/", {"phone_number": "0712345678", "code": "222222"})
        assert old_code.status_code == 400
        assert current_code.status_code == 200

    def test_superuser_has_admin_role_and_verified_phone(self):
        user = User.objects.create_superuser(phone_number="+254700000009", password="secure-test-password")
        assert user.role == User.Role.ADMIN
        assert user.phone_verified is True
        assert user.is_superuser is True
