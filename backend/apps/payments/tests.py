from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.core.models import AuditLog
from apps.properties.models import Property

from . import providers, services
from .models import Payment, ReferralFeeRule, ViewingCreditPurchase, ViewingPackage

CALLBACK_TOKEN = "t" * 40


class FakeProvider:
    """Stands in for Daraja. `answer` is what an STK Push Query returns."""

    name = "mpesa"

    def __init__(self):
        self.initiated = []
        self.answer = {"state": "success", "result_code": 0, "result_desc": "ok"}
        self.fail_initiate = False

    def initiate(self, *, amount, phone, reference, description=""):
        if self.fail_initiate:
            raise providers.MpesaError("M-Pesa did not accept the payment request.")
        self.initiated.append((amount, phone, reference))
        return {"checkout_request_id": f"ws_CO_{len(self.initiated)}_{reference}", "merchant_request_id": "m", "customer_message": "Check your phone"}

    def query(self, checkout_request_id, payment=None):
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture
def provider(monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(services, "get_provider", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def callback_settings(settings):
    settings.MPESA_CALLBACK_TOKEN = CALLBACK_TOKEN
    settings.MPESA_CALLBACK_ALLOWED_IPS = []


def tenant_client(phone="+254711000100"):
    user = User.objects.create_user(phone_number=phone, role=User.Role.TENANT)
    TenantProfile.objects.create(user=user)
    client = APIClient()
    client.force_authenticate(user)
    return user, client


def callback(payment, *, code=0, amount=None, receipt="QKX1234ABC"):
    body = {"Body": {"stkCallback": {"MerchantRequestID": "m", "CheckoutRequestID": payment.provider_reference,
                                     "ResultCode": code, "ResultDesc": "desc"}}}
    if code == 0:
        items = [{"Name": "Amount", "Value": payment.amount if amount is None else amount},
                 {"Name": "PhoneNumber", "Value": 254711000100}]
        if receipt:
            items.append({"Name": "MpesaReceiptNumber", "Value": receipt})
        body["Body"]["stkCallback"]["CallbackMetadata"] = {"Item": items}
    return APIClient().post(f"/api/v1/payments/mpesa/callback/{CALLBACK_TOKEN}/", body, format="json")


def buy(client, package, key="k1"):
    return client.post("/api/v1/payments/viewing-credits/", {"package_id": package.pk, "phone_number": "0711000100", "idempotency_key": key}, format="json")


def package(credits=5):
    return ViewingPackage.objects.get(country="KE", credits=credits, is_active=True)


# ------------------------------------------------------------------ Daraja adapter

def test_daraja_stk_push_builds_nairobi_password_and_a_routable_callback(monkeypatch):
    calls = []

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        if "/oauth/" in url:
            return {"access_token": "test-token"}
        return {"ResponseCode": "0", "CheckoutRequestID": "ws_CO_test", "CustomerMessage": "Check phone"}

    monkeypatch.setattr(providers, "_request", fake_request)
    with override_settings(
        MPESA_CONSUMER_KEY="key", MPESA_CONSUMER_SECRET="secret", MPESA_SHORTCODE="123456", MPESA_PASSKEY="passkey",
        MPESA_ENV="sandbox", MPESA_CALLBACK_URL="https://market.example/api/v1/payments/mpesa/callback",
        MPESA_CALLBACK_TOKEN="random-token",
    ):
        result = providers.MpesaDarajaProvider().initiate(amount=500, phone="254712345678", reference="fee-12")

    assert result["checkout_request_id"] == "ws_CO_test"
    payload = calls[1][1]["payload"]
    assert payload["Amount"] == 500 and payload["PhoneNumber"] == "254712345678"
    assert payload["Timestamp"].startswith("20")
    # Regression: the callback URL used to lack the trailing slash, so Django redirected Safaricom's POST and it was lost.
    path = payload["CallBackURL"].replace("https://market.example", "")
    assert path.endswith("/random-token/")
    assert resolve(path).url_name == "mpesa-callback"


def test_daraja_query_maps_result_codes(monkeypatch):
    answers = iter([{"access_token": "t"}, {"ResultCode": "1032", "ResultDesc": "Cancelled"},
                    {"access_token": "t"}, {"errorCode": "500.001.1001", "errorMessage": "The transaction is being processed"},
                    {"access_token": "t"}, {"ResultCode": "0", "ResultDesc": "ok"}])
    monkeypatch.setattr(providers, "_request", lambda url, **kwargs: next(answers))
    with override_settings(MPESA_CONSUMER_KEY="k", MPESA_CONSUMER_SECRET="s", MPESA_SHORTCODE="1", MPESA_PASSKEY="p",
                           MPESA_CALLBACK_URL="https://x", MPESA_CALLBACK_TOKEN="t"):
        daraja = providers.MpesaDarajaProvider()
        assert daraja.query("ws")["state"] == "cancelled"
        assert daraja.query("ws")["state"] == "pending"
        assert daraja.query("ws")["state"] == "success"


@override_settings(DEBUG=False)
def test_simulator_refuses_to_run_without_debug():
    with pytest.raises(providers.MpesaError):
        providers.SimulatorProvider().initiate(amount=50, phone="254711000000", reference="x")


# ------------------------------------------------------------------ prices

@pytest.mark.django_db
def test_price_list_is_public_and_comes_from_the_database():
    response = APIClient().get("/api/v1/payments/prices/")
    assert response.status_code == 200
    assert [(p["credits"], p["price"]) for p in response.data["viewing_packages"]] == [(1, 50), (2, 100), (5, 150), (10, 250)]
    assert response.data["property_verification_fee"] == {"amount": 2000, "currency": "KES"}
    assert response.data["package_conditions"]

    ViewingPackage.objects.filter(credits=2).update(is_active=False)
    ViewingPackage.objects.create(country="KE", name="Three", credits=3, price=120)
    response = APIClient().get("/api/v1/payments/prices/")
    assert [(p["credits"], p["price"]) for p in response.data["viewing_packages"]] == [(1, 50), (3, 120), (5, 150), (10, 250)]


@pytest.mark.django_db
def test_referral_fee_rules_support_fixed_and_percentage_fees():
    assert services.referral_fee_for(14_999) == 1_500
    assert services.referral_fee_for(60_001) == 6_000
    ReferralFeeRule.objects.filter(country="KE").update(is_active=False)
    ReferralFeeRule.objects.create(country="KE", min_rent=0, fee_type="percent", percent="10.00")
    assert services.referral_fee_for(25_000) == 2_500


# ------------------------------------------------------------------ buying credits

@pytest.mark.django_db
class TestViewingCreditPurchase:
    def test_credits_are_granted_only_after_a_confirmed_callback(self, provider):
        user, client = tenant_client()
        response = buy(client, package(5))
        assert response.status_code == 202 and response.data["status"] == "pending"
        assert client.get("/api/v1/payments/viewing-credits/").data["balance"] == 0

        payment = Payment.objects.get()
        assert payment.amount == 150 and payment.package.credits == 5
        assert callback(payment).status_code == 200
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCESSFUL and payment.provider_receipt == "QKX1234ABC"
        assert client.get("/api/v1/payments/viewing-credits/").data["balance"] == 5
        assert user.notifications.filter(event="payment.successful", channel="in_app").exists()

    def test_duplicate_callbacks_never_grant_credits_twice(self, provider):
        user, client = tenant_client()
        buy(client, package(5))
        payment = Payment.objects.get()
        callback(payment)
        callback(payment)
        assert ViewingCreditPurchase.objects.count() == 1
        assert client.get("/api/v1/payments/viewing-credits/").data["balance"] == 5

    def test_the_same_idempotency_key_returns_the_original_payment(self, provider):
        _, client = tenant_client()
        first = buy(client, package(5), key="retry-me")
        second = buy(client, package(5), key="retry-me")
        assert first.data["id"] == second.data["id"]
        assert len(provider.initiated) == 1
        assert buy(client, package(10), key="retry-me").status_code == 400

    def test_users_cannot_collide_on_idempotency_keys(self, provider):
        _, alice = tenant_client("+254711000101")
        _, bob = tenant_client("+254711000102")
        assert buy(alice, package(5), key="same").status_code == 202
        assert buy(bob, package(5), key="same").status_code == 202
        assert Payment.objects.count() == 2

    def test_a_fresh_pending_payment_blocks_a_second_prompt(self, provider):
        _, client = tenant_client()
        buy(client, package(5), key="a")
        provider.answer = {"state": "pending", "result_code": None, "result_desc": ""}
        response = buy(client, package(1), key="b")
        assert response.status_code == 409 and response.data["error"]["code"] == "bundle_payment_pending"

    def test_a_lost_callback_no_longer_blocks_the_tenant(self, provider, settings):
        """Regression: a pending payment that never got a callback used to block purchases forever."""
        _, client = tenant_client()
        buy(client, package(5), key="a")
        payment = Payment.objects.get()
        provider.answer = {"state": "pending", "result_code": None, "result_desc": ""}
        Payment.objects.filter(pk=payment.pk).update(created_at=timezone.now() - timedelta(minutes=settings.PAYMENT_TIMEOUT_MINUTES + 1))
        response = buy(client, package(1), key="b")
        assert response.status_code == 202
        payment.refresh_from_db()
        assert payment.status == Payment.Status.FAILED and payment.failure_reason == "timeout"

    def test_a_late_success_after_timeout_is_still_honoured(self, provider):
        _, client = tenant_client()
        buy(client, package(2))
        payment = Payment.objects.get()
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.FAILED, failure_reason="timeout")
        callback(payment)
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCESSFUL
        assert client.get("/api/v1/payments/viewing-credits/").data["balance"] == 2

    def test_reconciliation_uses_the_provider_answer_when_the_callback_is_missing(self, provider):
        _, client = tenant_client()
        buy(client, package(10))
        payment = Payment.objects.get()
        Payment.objects.filter(pk=payment.pk).update(created_at=timezone.now() - timedelta(minutes=3))
        assert services.reconcile_stale_payments() == {"successful": 1}
        assert client.get("/api/v1/payments/viewing-credits/").data["balance"] == 10

    def test_payer_cancellation_and_failure_are_recorded_without_credits(self, provider):
        _, client = tenant_client()
        buy(client, package(5), key="a")
        first = Payment.objects.get()
        callback(first, code=1032)
        first.refresh_from_db()
        assert first.status == Payment.Status.CANCELLED
        buy(client, package(5), key="b")
        second = Payment.objects.exclude(pk=first.pk).get()
        callback(second, code=2001)
        second.refresh_from_db()
        assert second.status == Payment.Status.FAILED
        assert ViewingCreditPurchase.objects.count() == 0

    def test_provider_error_is_reported_and_does_not_block_a_retry(self, provider):
        _, client = tenant_client()
        provider.fail_initiate = True
        response = buy(client, package(5), key="a")
        assert response.status_code == 503
        assert Payment.objects.get().status == Payment.Status.FAILED
        provider.fail_initiate = False
        assert buy(client, package(5), key="b").status_code == 202

    def test_only_tenants_buy_packages(self, provider):
        landlord = User.objects.create_user(phone_number="+254722000100", role=User.Role.LANDLORD)
        client = APIClient(); client.force_authenticate(landlord)
        assert client.post("/api/v1/payments/viewing-credits/", {"package_id": package(5).pk, "phone_number": "0722000100"}, format="json").status_code == 403


# ------------------------------------------------------------------ callback verification

@pytest.mark.django_db
class TestCallbackVerification:
    def _pending(self, provider):
        _, client = tenant_client()
        buy(client, package(5))
        return Payment.objects.get()

    def test_wrong_token_is_rejected(self, provider):
        payment = self._pending(provider)
        response = APIClient().post("/api/v1/payments/mpesa/callback/wrong/", {"Body": {}}, format="json")
        assert response.status_code == 404
        payment.refresh_from_db()
        assert payment.status == Payment.Status.PENDING

    def test_success_callback_contradicted_by_the_provider_grants_nothing(self, provider):
        payment = self._pending(provider)
        provider.answer = {"state": "failed", "result_code": 1, "result_desc": "Insufficient funds"}
        callback(payment)
        payment.refresh_from_db()
        assert payment.status == Payment.Status.DISPUTED and payment.failure_reason == "confirmation_mismatch"
        assert ViewingCreditPurchase.objects.count() == 0

    def test_unconfirmable_callback_waits_for_reconciliation(self, provider):
        payment = self._pending(provider)
        provider.answer = providers.MpesaError("down")
        callback(payment)
        payment.refresh_from_db()
        assert payment.status == Payment.Status.PENDING and payment.callback_received_at
        provider.answer = {"state": "success", "result_code": 0, "result_desc": "ok"}
        services.reconcile_payment(payment.pk)
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCESSFUL and payment.provider_receipt == "QKX1234ABC"

    def test_amount_mismatch_is_flagged_for_review(self, provider):
        payment = self._pending(provider)
        callback(payment, amount=1)
        payment.refresh_from_db()
        assert payment.status == Payment.Status.DISPUTED and payment.failure_reason == "amount_mismatch"
        assert ViewingCreditPurchase.objects.count() == 0

    def test_one_receipt_cannot_settle_two_payments(self, provider):
        _, client = tenant_client()
        buy(client, package(5), key="a")
        first = Payment.objects.get()
        callback(first, receipt="SAME")
        buy(client, package(1), key="b")
        second = Payment.objects.exclude(pk=first.pk).get()
        callback(second, receipt="SAME")
        second.refresh_from_db()
        assert second.status == Payment.Status.DISPUTED and second.failure_reason == "duplicate_receipt"
        assert ViewingCreditPurchase.objects.count() == 1

    def test_unknown_checkout_is_acknowledged_without_changes(self, provider):
        body = {"Body": {"stkCallback": {"CheckoutRequestID": "nope", "ResultCode": 0}}}
        assert APIClient().post(f"/api/v1/payments/mpesa/callback/{CALLBACK_TOKEN}/", body, format="json").status_code == 200

    def test_malformed_callback_is_rejected(self, provider):
        assert APIClient().post(f"/api/v1/payments/mpesa/callback/{CALLBACK_TOKEN}/", {"x": 1}, format="json").status_code == 400

    def test_ip_allowlist_when_configured(self, provider, settings):
        payment = self._pending(provider)
        settings.MPESA_CALLBACK_ALLOWED_IPS = ["196.201.214.0/24"]
        assert callback(payment).status_code == 404
        payment.refresh_from_db()
        assert payment.status == Payment.Status.PENDING

    def test_payment_status_is_read_only_and_private(self, provider):
        user, client = tenant_client("+254711000150")
        buy(client, package(5))
        payment = Payment.objects.get()
        assert client.get(f"/api/v1/payments/{payment.pk}/").data["status"] == "pending"
        assert client.patch(f"/api/v1/payments/{payment.pk}/", {"status": "successful"}, format="json").status_code == 405
        _, other = tenant_client("+254711000151")
        assert other.get(f"/api/v1/payments/{payment.pk}/").status_code == 404


# ------------------------------------------------------------------ verification fee & refunds

@pytest.mark.django_db
def test_verification_fee_uses_the_configured_price_and_moves_property_to_review(provider):
    landlord_user = User.objects.create_user(phone_number="+254722000200", role=User.Role.LANDLORD)
    prop = Property.objects.create(landlord=LandlordProfile.objects.create(user=landlord_user), name="P", address_line="1",
                                   area="Kilimani", city="Nairobi", county="Nairobi")
    client = APIClient(); client.force_authenticate(landlord_user)
    response = client.post(f"/api/v1/payments/property-verification/{prop.pk}/pay/", {"phone_number": "0722000200"}, format="json")
    assert response.status_code == 202
    payment = Payment.objects.get()
    assert payment.amount == 2000
    callback(payment)
    prop.refresh_from_db()
    assert prop.verification_status == Property.VerificationStatus.PENDING

    other = User.objects.create_user(phone_number="+254722000201", role=User.Role.LANDLORD)
    client.force_authenticate(other)
    assert client.post(f"/api/v1/payments/property-verification/{prop.pk}/pay/", {"phone_number": "0722000201"}, format="json").status_code == 404


@pytest.mark.django_db
def test_recording_a_refund_revokes_unused_credits_and_is_audited(provider):
    user, client = tenant_client()
    buy(client, package(5))
    payment = Payment.objects.get()
    callback(payment)
    admin = User.objects.create_superuser(phone_number="+254700000900", password="x-secure-password")
    services.record_refund(payment.pk, admin=admin, reason="Customer request")
    payment.refresh_from_db()
    assert payment.status == Payment.Status.REFUNDED and payment.refunded_by == admin
    assert client.get("/api/v1/payments/viewing-credits/").data["balance"] == 0
    entry = AuditLog.objects.get(action="payment.refunded")
    assert entry.metadata["credits_revoked"] == 5
