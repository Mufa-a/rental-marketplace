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
            "/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant", "accept_terms": True}
        )
        assert response.status_code == 200
        user = User.objects.get(phone_number="+254712345678")
        assert user.is_active is False
        assert OTPCode.objects.filter(user=user).exists()

    def test_wrong_code_is_rejected_and_counted(self):
        client = APIClient()
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant", "accept_terms": True})
        response = client.post(
            "/api/v1/auth/otp/verify/", {"phone_number": "0712345678", "code": "000000"}
        )
        assert response.status_code == 400
        otp = OTPCode.objects.latest("created_at")
        assert otp.failed_attempts == 1

    def test_five_wrong_codes_locks_out_further_attempts(self):
        client = APIClient()
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant", "accept_terms": True})
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
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant", "accept_terms": True})
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
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant", "accept_terms": True})
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



@pytest.mark.django_db
class TestConsentAndAccountSafety:
    def test_new_account_requires_terms_acceptance(self):
        response = APIClient().post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "role": "tenant"}, format="json")
        assert response.status_code == 400
        assert response.data["error"]["code"] == "terms_required"
        assert not User.objects.filter(phone_number="+254712345678").exists()

    def test_signup_records_terms_consent_and_keeps_marketing_separate(self):
        from apps.accounts.models import ConsentRecord

        APIClient().post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "accept_terms": True, "policy_version": "v-test"}, format="json")
        user = User.objects.get(phone_number="+254712345678")
        records = list(user.consents.all())
        assert [(r.consent_type, r.granted, r.policy_version) for r in records] == [("terms_privacy", True, "v-test")]
        assert not user.consents.filter(consent_type=ConsentRecord.ConsentType.MARKETING).exists()

    def test_marketing_opt_in_is_recorded_only_when_chosen(self):
        APIClient().post("/api/v1/auth/otp/request/", {"phone_number": "0712345678", "accept_terms": True, "marketing_opt_in": True}, format="json")
        user = User.objects.get(phone_number="+254712345678")
        assert user.consents.filter(consent_type="marketing", granted=True).exists()

    def test_existing_user_can_sign_in_without_reaccepting_terms(self):
        User.objects.create_user(username="+254712345678", phone_number="+254712345678", role="tenant", phone_verified=True)
        response = APIClient().post("/api/v1/auth/otp/request/", {"phone_number": "0712345678"}, format="json")
        assert response.status_code == 200

    def test_suspended_account_cannot_reactivate_itself_with_an_otp(self, monkeypatch):
        import apps.accounts.services as services

        monkeypatch.setattr(services, "generate_otp_code", lambda: "111111")
        user = User.objects.create_user(username="+254712345678", phone_number="+254712345678", role="tenant", phone_verified=True, is_active=True)
        client = APIClient()
        client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678"}, format="json")
        # An administrator suspends the account after a code was issued.
        user.is_active = False
        user.save(update_fields=["is_active"])
        verify = client.post("/api/v1/auth/otp/verify/", {"phone_number": "0712345678", "code": "111111"}, format="json")
        assert verify.status_code == 403
        assert "access" not in verify.data
        request_again = client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345678"}, format="json")
        assert request_again.status_code == 403
        user.refresh_from_db()
        assert user.is_active is False

    def test_verify_does_not_reveal_whether_a_number_has_an_account(self):
        response = APIClient().post("/api/v1/auth/otp/verify/", {"phone_number": "0799999999", "code": "123456"}, format="json")
        assert response.status_code == 400
        assert response.data["error"]["code"] == "otp_invalid"

    def test_consent_can_be_read_and_changed_but_terms_cannot_be_withdrawn(self):
        user = User.objects.create_user(username="u1", phone_number="+254712345670", role="tenant")
        client = APIClient()
        client.force_authenticate(user)
        assert client.post("/api/v1/auth/consents/", {"consent_type": "location", "granted": True}, format="json").status_code == 201
        assert client.post("/api/v1/auth/consents/", {"consent_type": "location", "granted": False}, format="json").status_code == 201
        state = {row["consent_type"]: row["granted"] for row in client.get("/api/v1/auth/consents/").data}
        assert state["location"] is False
        assert client.post("/api/v1/auth/consents/", {"consent_type": "terms_privacy", "granted": False}, format="json").status_code == 400
        assert APIClient().get("/api/v1/auth/consents/").status_code == 401

    def test_deletion_request_needs_confirmation_and_is_reviewed_by_a_human(self):
        from apps.accounts.models import AccountDeletionRequest

        user = User.objects.create_user(username="u2", phone_number="+254712345671", role="tenant")
        client = APIClient()
        client.force_authenticate(user)
        wrong = client.post("/api/v1/auth/deletion-request/", {"confirm_phone": "0700000000"}, format="json")
        assert wrong.status_code == 400
        ok = client.post("/api/v1/auth/deletion-request/", {"confirm_phone": "0712345671", "reason": "No longer renting"}, format="json")
        assert ok.status_code == 201
        assert ok.data["status"] == "pending"
        assert ok.data["may_be_retained"]
        assert client.post("/api/v1/auth/deletion-request/", {"confirm_phone": "0712345671"}, format="json").status_code == 409
        # Nothing was deleted automatically.
        assert User.objects.filter(pk=user.pk, is_active=True).exists()
        assert client.delete("/api/v1/auth/deletion-request/").status_code == 204
        assert AccountDeletionRequest.objects.get().status == "cancelled"

    def test_deletion_request_endpoint_only_shows_own_request(self):
        first = User.objects.create_user(username="u3", phone_number="+254712345672", role="tenant")
        second = User.objects.create_user(username="u4", phone_number="+254712345673", role="tenant")
        client = APIClient()
        client.force_authenticate(first)
        client.post("/api/v1/auth/deletion-request/", {"confirm_phone": "0712345672"}, format="json")
        client.force_authenticate(second)
        assert client.get("/api/v1/auth/deletion-request/").data["request"] is None
        assert client.delete("/api/v1/auth/deletion-request/").status_code == 404
