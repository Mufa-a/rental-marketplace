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


@pytest.mark.django_db
def test_otp_verification_is_throttled_per_phone_across_codes():
    from rest_framework.test import APIClient as Client
    client = Client()
    payload = {"phone_number": "0712000999", "code": "000000"}
    codes = [client.post("/api/v1/auth/otp/verify/", payload, format="json").status_code for _ in range(12)]
    assert codes[:10] == [400] * 10 and codes[-1] == 429


def _sign_in(client, monkeypatch, phone="0712345600", role="tenant"):
    import apps.accounts.services as services
    monkeypatch.setattr(services, "generate_otp_code", lambda: "111111")
    client.post("/api/v1/auth/otp/request/", {"phone_number": phone, "role": role, "accept_terms": True})
    return client.post("/api/v1/auth/otp/verify/", {"phone_number": phone, "code": "111111"})


@pytest.mark.django_db
class TestCookieSessions:
    def test_refresh_token_is_only_in_an_httponly_strict_cookie(self, monkeypatch):
        client = APIClient()
        response = _sign_in(client, monkeypatch)
        assert response.status_code == 200 and "access" in response.data and "refresh" not in response.data
        cookie = response.cookies["nyumbani_refresh"]
        assert cookie["httponly"] and cookie["samesite"] == "Strict" and cookie["path"] == "/api/v1/auth/"

    def test_refresh_rotates_the_cookie_and_the_old_token_stops_working(self, monkeypatch):
        client = APIClient()
        first = _sign_in(client, monkeypatch).cookies["nyumbani_refresh"].value
        refreshed = client.post("/api/v1/auth/token/refresh/")
        assert refreshed.status_code == 200 and "access" in refreshed.data
        assert refreshed.cookies["nyumbani_refresh"].value != first
        stale = APIClient()
        stale.cookies["nyumbani_refresh"] = first
        assert stale.post("/api/v1/auth/token/refresh/").status_code == 401

    def test_suspended_users_cannot_refresh(self, monkeypatch):
        client = APIClient()
        _sign_in(client, monkeypatch)
        User.objects.filter(phone_number="+254712345600").update(is_active=False)
        response = client.post("/api/v1/auth/token/refresh/")
        assert response.status_code == 401 and response.cookies["nyumbani_refresh"].value == ""

    def test_logout_blacklists_and_clears_even_with_an_expired_access_token(self, monkeypatch):
        client = APIClient()
        token = _sign_in(client, monkeypatch).cookies["nyumbani_refresh"].value
        response = client.post("/api/v1/auth/logout/")
        assert response.status_code == 204 and response.cookies["nyumbani_refresh"].value == ""
        replay = APIClient()
        replay.cookies["nyumbani_refresh"] = token
        assert replay.post("/api/v1/auth/token/refresh/").status_code == 401

    def test_otp_request_does_not_reveal_whether_the_number_is_registered(self, monkeypatch):
        client = APIClient()
        new = client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345601", "accept_terms": True}).data
        _sign_in(client, monkeypatch, phone="0712345602")
        existing = client.post("/api/v1/auth/otp/request/", {"phone_number": "0712345602"}).data
        assert set(new) == set(existing) == {"phone_number", "expires_in_minutes"}

    def test_credentialed_cors_is_limited_to_configured_origins(self):
        ok = APIClient().options("/api/v1/auth/token/refresh/", HTTP_ORIGIN="http://localhost:3000", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        assert ok["Access-Control-Allow-Credentials"] == "true" and ok["Access-Control-Allow-Origin"] == "http://localhost:3000"
        evil = APIClient().options("/api/v1/auth/token/refresh/", HTTP_ORIGIN="https://evil.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        assert "Access-Control-Allow-Origin" not in evil


@pytest.mark.django_db
class TestStaffMFA:
    def _admin(self):
        return User.objects.create_superuser(phone_number="+254712345699", password="x-secure-password-1")

    SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"

    def _enrol(self, user):
        """Run the operator command exactly as documented, typing the app's current code at the prompt."""
        from io import StringIO
        from unittest import mock

        import pyotp
        from django.core.management import call_command

        from apps.accounts import mfa as mfa_module

        out = StringIO()
        with mock.patch("pyotp.random_base32", return_value=self.SECRET), \
                mock.patch("builtins.input", side_effect=lambda prompt: pyotp.TOTP(self.SECRET).now()):
            call_command("enroll_staff_totp", user.phone_number, stdout=out)
        assert "confirmed" in out.getvalue()
        device = user.__class__.objects.get(pk=user.pk).totp_device
        assert self.SECRET not in device.secret_encrypted  # encrypted at rest
        assert mfa_module.decrypt_secret(device.secret_encrypted) == self.SECRET
        # The confirmation code used up the current 30-second step; reset so the sign-in below can use a fresh code.
        type(device).objects.filter(pk=device.pk).update(last_used_step=0)
        return self.SECRET

    def test_admin_sign_in_requires_an_enrolled_authenticator(self, settings, monkeypatch):
        settings.STAFF_MFA_REQUIRED = True
        self._admin()
        response = _sign_in(APIClient(), monkeypatch, phone="0712345699")
        assert response.status_code == 403 and response.data["error"]["code"] == "mfa_enrolment_required"
        assert "nyumbani_refresh" not in response.cookies

    def test_admin_gets_a_session_only_after_a_valid_totp_and_codes_cannot_be_replayed(self, settings, monkeypatch):
        import pyotp
        settings.STAFF_MFA_REQUIRED = True
        secret = self._enrol(self._admin())
        client = APIClient()
        first = _sign_in(client, monkeypatch, phone="0712345699")
        assert first.data["mfa_required"] is True and "access" not in first.data and "nyumbani_refresh" not in first.cookies
        ticket = first.data["mfa_ticket"]
        assert client.post("/api/v1/auth/mfa/verify/", {"mfa_ticket": ticket, "code": "000000"}).status_code == 400
        code = pyotp.TOTP(secret).now()
        ok = client.post("/api/v1/auth/mfa/verify/", {"mfa_ticket": ticket, "code": code})
        assert ok.status_code == 200 and "access" in ok.data and ok.cookies["nyumbani_refresh"].value
        assert client.post("/api/v1/auth/mfa/verify/", {"mfa_ticket": ticket, "code": code}).status_code == 400  # replay
        assert client.post("/api/v1/auth/mfa/verify/", {"mfa_ticket": "forged", "code": code}).status_code == 400

    def test_tenants_and_landlords_are_never_asked_for_a_second_factor(self, settings, monkeypatch):
        settings.STAFF_MFA_REQUIRED = True
        response = _sign_in(APIClient(), monkeypatch, phone="0712345698", role="landlord")
        assert response.status_code == 200 and "access" in response.data
