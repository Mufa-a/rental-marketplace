"""Money-critical paths: the Safaricom callback and the endpoints that start a payment."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.core.models import AuditLog
from apps.properties.models import Property, Unit
from apps.referrals.models import ReferralFee
from apps.referrals.services import create_fee_for_rented_viewing
from apps.viewings.models import Viewing, ViewingRequest

from . import views
from .models import Payment, ViewingCreditPurchase
from .services import MpesaError

TOKEN = "callback-secret"
CALLBACK_URL = f"/api/v1/payments/mpesa/callback/{TOKEN}/"


@pytest.fixture(autouse=True)
def mpesa_token(settings):
    settings.MPESA_CALLBACK_TOKEN = TOKEN


def callback_body(checkout_id, *, code=0, amount=100, receipt="QWE123RTY", description="The service request is processed successfully."):
    callback = {"CheckoutRequestID": checkout_id, "ResultCode": code, "ResultDesc": description}
    if code == 0:
        items = []
        if amount is not None:
            items.append({"Name": "Amount", "Value": amount})
        if receipt is not None:
            items.append({"Name": "MpesaReceiptNumber", "Value": receipt})
        callback["CallbackMetadata"] = {"Item": items}
    return {"Body": {"stkCallback": callback}}


def make_user(role, phone):
    return User.objects.create_user(username=phone, phone_number=phone, role=role)


@pytest.fixture
def tenant_user(db):
    user = make_user("tenant", "+254711000101")
    TenantProfile.objects.create(user=user)
    return user


@pytest.fixture
def landlord(db):
    user = make_user("landlord", "+254722000101")
    return LandlordProfile.objects.create(user=user)


@pytest.fixture
def prop(landlord):
    return Property.objects.create(landlord=landlord, name="Home", address_line="1 Road", area="Westlands", city="Nairobi", county="Nairobi")


@pytest.fixture
def unit(prop):
    return Unit.objects.create(property=prop, unit_number="1", title="Studio", unit_type="studio", monthly_rent=20000, is_published=True)


def pending_payment(checkout_id="ws_CO_1", **fields):
    defaults = dict(amount=100, phone_number="+254711000101", provider_reference=checkout_id, idempotency_key=f"key-{checkout_id}")
    defaults.update(fields)
    return Payment.objects.create(**defaults)


def credits_payment(tenant_user, checkout_id="ws_CO_credits", credits=3, amount=100):
    return pending_payment(
        checkout_id, purpose=Payment.Purpose.VIEWING_CREDITS, tenant_user=tenant_user, credits=credits, amount=amount,
    )


def make_fee(landlord, unit):
    tenant = TenantProfile.objects.create(user=make_user("tenant", "+254711000199"))
    viewing_request = ViewingRequest.objects.create(tenant=tenant, unit=unit, status=ViewingRequest.Status.APPROVED)
    viewing = Viewing.objects.create(request=viewing_request, scheduled_at=timezone.now() + timedelta(hours=1), status=Viewing.Status.RENTED)
    fee, _ = create_fee_for_rented_viewing(viewing)
    return fee


def post_callback(client, body, url=CALLBACK_URL):
    return client.post(url, body, format="json")


@pytest.mark.django_db
class TestCallbackSecurityAndShape:
    def test_wrong_token_is_rejected_and_nothing_changes(self, tenant_user):
        payment = credits_payment(tenant_user)
        response = post_callback(APIClient(), callback_body("ws_CO_credits"), url="/api/v1/payments/mpesa/callback/not-the-token/")
        assert response.status_code == 404
        payment.refresh_from_db()
        assert payment.status == Payment.Status.PENDING
        assert not ViewingCreditPurchase.objects.exists()

    def test_callback_is_refused_when_no_token_is_configured(self, settings, tenant_user):
        settings.MPESA_CALLBACK_TOKEN = ""
        credits_payment(tenant_user)
        response = post_callback(APIClient(), callback_body("ws_CO_credits"), url="/api/v1/payments/mpesa/callback/anything/")
        assert response.status_code == 404
        assert not ViewingCreditPurchase.objects.exists()

    @pytest.mark.parametrize("body", [{}, {"Body": {}}, {"Body": {"stkCallback": {"CheckoutRequestID": "x", "ResultCode": "not-a-number"}}}])
    def test_malformed_payload_returns_400(self, body):
        assert post_callback(APIClient(), body).status_code == 400

    def test_unknown_checkout_id_returns_404(self, db):
        assert post_callback(APIClient(), callback_body("ws_CO_nobody")).status_code == 404


@pytest.mark.django_db
class TestViewingCreditCallback:
    def test_success_creates_the_credit_purchase_and_audit_entry(self, tenant_user):
        payment = credits_payment(tenant_user, credits=5, amount=150)
        response = post_callback(APIClient(), callback_body("ws_CO_credits", amount=150))
        assert response.status_code == 200 and response.data["ResultCode"] == 0
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCESSFUL
        assert payment.provider_payload["receipt"] == "QWE123RTY"
        purchase = ViewingCreditPurchase.objects.get(payment=payment)
        assert purchase.credits_total == 5 and purchase.credits_remaining == 5
        assert AuditLog.objects.filter(action="payment.successful", object_id=str(payment.pk)).exists()

    def test_replaying_the_same_callback_does_not_grant_credits_twice(self, tenant_user):
        credits_payment(tenant_user)
        client = APIClient()
        post_callback(client, callback_body("ws_CO_credits"))
        replay = post_callback(client, callback_body("ws_CO_credits"))
        assert replay.status_code == 200
        assert ViewingCreditPurchase.objects.count() == 1
        assert AuditLog.objects.filter(action="payment.successful").count() == 1

    def test_wrong_amount_is_disputed_and_grants_nothing(self, tenant_user):
        payment = credits_payment(tenant_user, amount=100)
        post_callback(APIClient(), callback_body("ws_CO_credits", amount=10))
        payment.refresh_from_db()
        assert payment.status == Payment.Status.DISPUTED
        assert not ViewingCreditPurchase.objects.exists()

    def test_missing_receipt_is_disputed(self, tenant_user):
        payment = credits_payment(tenant_user)
        post_callback(APIClient(), callback_body("ws_CO_credits", receipt=None))
        payment.refresh_from_db()
        assert payment.status == Payment.Status.DISPUTED
        assert not ViewingCreditPurchase.objects.exists()

    def test_failed_or_cancelled_prompt_marks_payment_failed(self, tenant_user):
        payment = credits_payment(tenant_user)
        post_callback(APIClient(), callback_body("ws_CO_credits", code=1032, description="Request cancelled by user"))
        payment.refresh_from_db()
        assert payment.status == Payment.Status.FAILED
        assert payment.provider_payload["result_code"] == 1032
        assert not ViewingCreditPurchase.objects.exists()

    def test_late_failure_cannot_undo_a_successful_payment(self, tenant_user):
        payment = credits_payment(tenant_user)
        client = APIClient()
        post_callback(client, callback_body("ws_CO_credits"))
        post_callback(client, callback_body("ws_CO_credits", code=1, description="Insufficient funds"))
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCESSFUL
        assert ViewingCreditPurchase.objects.count() == 1


@pytest.mark.django_db
class TestReferralFeeCallback:
    def test_success_marks_the_fee_paid(self, landlord, unit):
        fee = make_fee(landlord, unit)
        pending_payment("ws_CO_fee", fee=fee, purpose=Payment.Purpose.REFERRAL_FEE, amount=fee.amount)
        post_callback(APIClient(), callback_body("ws_CO_fee", amount=fee.amount))
        fee.refresh_from_db()
        assert fee.status == ReferralFee.Status.PAID

    def test_failure_leaves_the_fee_payable(self, landlord, unit):
        fee = make_fee(landlord, unit)
        payment = pending_payment("ws_CO_fee", fee=fee, purpose=Payment.Purpose.REFERRAL_FEE, amount=fee.amount)
        post_callback(APIClient(), callback_body("ws_CO_fee", code=2001, description="Wrong PIN"))
        fee.refresh_from_db(); payment.refresh_from_db()
        assert fee.status == ReferralFee.Status.PENDING and payment.status == Payment.Status.FAILED

    def test_wrong_amount_does_not_mark_the_fee_paid(self, landlord, unit):
        fee = make_fee(landlord, unit)
        pending_payment("ws_CO_fee", fee=fee, purpose=Payment.Purpose.REFERRAL_FEE, amount=fee.amount)
        post_callback(APIClient(), callback_body("ws_CO_fee", amount=1))
        fee.refresh_from_db()
        assert fee.status == ReferralFee.Status.PENDING


@pytest.mark.django_db
class TestVerificationFeeCallback:
    def _payment(self, prop):
        return pending_payment("ws_CO_verify", purpose=Payment.Purpose.VERIFICATION_FEE, property=prop, amount=2000)

    def test_success_moves_an_unverified_property_to_pending_review(self, prop):
        self._payment(prop)
        post_callback(APIClient(), callback_body("ws_CO_verify", amount=2000))
        prop.refresh_from_db()
        assert prop.verification_status == Property.VerificationStatus.PENDING

    def test_success_does_not_downgrade_an_already_verified_property(self, prop):
        prop.verification_status = Property.VerificationStatus.VERIFIED
        prop.save(update_fields=["verification_status"])
        self._payment(prop)
        post_callback(APIClient(), callback_body("ws_CO_verify", amount=2000))
        prop.refresh_from_db()
        assert prop.verification_status == Property.VerificationStatus.VERIFIED

    def test_failure_leaves_the_property_unverified(self, prop):
        self._payment(prop)
        post_callback(APIClient(), callback_body("ws_CO_verify", code=1032))
        prop.refresh_from_db()
        assert prop.verification_status == Property.VerificationStatus.UNVERIFIED


@pytest.fixture
def stk_ok(monkeypatch):
    calls = []

    def fake(*, amount, phone, reference):
        calls.append({"amount": amount, "phone": phone, "reference": reference})
        return {"CheckoutRequestID": f"ws_CO_{len(calls)}", "MerchantRequestID": "m-1", "CustomerMessage": "Check your phone"}

    monkeypatch.setattr(views, "initiate_stk_push", fake)
    return calls


@pytest.fixture
def stk_down(monkeypatch):
    def fake(**kwargs):
        raise MpesaError("The M-Pesa service could not be reached.")

    monkeypatch.setattr(views, "initiate_stk_push", fake)


def authed(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
class TestStartingBundlePayments:
    def test_tenant_starts_a_bundle_payment(self, tenant_user, stk_ok):
        response = authed(tenant_user).post("/api/v1/payments/viewing-credits/", {"credits": 3, "phone_number": "0712345678"}, format="json")
        assert response.status_code == 202
        payment = Payment.objects.get()
        assert payment.amount == 100 and payment.credits == 3 and payment.provider_reference == "ws_CO_1"
        assert stk_ok[0]["amount"] == 100 and stk_ok[0]["phone"] == "254712345678"

    def test_only_tenants_can_buy_bundles(self, landlord, stk_ok):
        response = authed(landlord.user).post("/api/v1/payments/viewing-credits/", {"credits": 1, "phone_number": "0712345678"}, format="json")
        assert response.status_code == 403 and not stk_ok

    def test_unknown_bundle_size_is_rejected(self, tenant_user, stk_ok):
        response = authed(tenant_user).post("/api/v1/payments/viewing-credits/", {"credits": 2, "phone_number": "0712345678"}, format="json")
        assert response.status_code == 400 and not stk_ok

    def test_second_purchase_is_blocked_while_one_is_pending(self, tenant_user, stk_ok):
        client = authed(tenant_user)
        first = client.post("/api/v1/payments/viewing-credits/", {"credits": 1, "phone_number": "0712345678"}, format="json")
        second = client.post("/api/v1/payments/viewing-credits/", {"credits": 5, "phone_number": "0712345678"}, format="json")
        assert first.status_code == 202
        assert second.status_code == 409 and second.data["error"]["code"] == "bundle_payment_pending"
        assert len(stk_ok) == 1

    def test_provider_outage_marks_payment_failed_and_returns_503(self, tenant_user, stk_down):
        response = authed(tenant_user).post("/api/v1/payments/viewing-credits/", {"credits": 1, "phone_number": "0712345678"}, format="json")
        assert response.status_code == 503
        assert Payment.objects.get().status == Payment.Status.FAILED

    def test_reusing_an_idempotency_key_for_another_bundle_conflicts(self, tenant_user, stk_ok):
        client = authed(tenant_user)
        client.post("/api/v1/payments/viewing-credits/", {"credits": 1, "phone_number": "0712345678", "idempotency_key": "same"}, format="json")
        Payment.objects.update(status=Payment.Status.FAILED)
        again = client.post("/api/v1/payments/viewing-credits/", {"credits": 10, "phone_number": "0712345678", "idempotency_key": "same"}, format="json")
        assert again.status_code == 409 and again.data["error"]["code"] == "idempotency_conflict"
        assert Payment.objects.count() == 1


@pytest.mark.django_db
class TestStartingFeeAndVerificationPayments:
    def test_landlord_can_pay_their_own_fee_but_not_someone_elses(self, landlord, unit, stk_ok):
        fee = make_fee(landlord, unit)
        other = make_user("landlord", "+254722000102")
        LandlordProfile.objects.create(user=other)
        assert authed(other).post(f"/api/v1/payments/referral-fees/{fee.id}/pay/", {"phone_number": "0722000102"}, format="json").status_code == 404
        mine = authed(landlord.user).post(f"/api/v1/payments/referral-fees/{fee.id}/pay/", {"phone_number": "0722000101"}, format="json")
        assert mine.status_code == 202
        assert Payment.objects.get(fee=fee).amount == fee.amount

    def test_an_already_paid_fee_cannot_be_paid_again(self, landlord, unit, stk_ok):
        fee = make_fee(landlord, unit)
        fee.status = ReferralFee.Status.PAID
        fee.save(update_fields=["status"])
        response = authed(landlord.user).post(f"/api/v1/payments/referral-fees/{fee.id}/pay/", {"phone_number": "0722000101"}, format="json")
        assert response.status_code == 409 and response.data["error"]["code"] == "already_paid" and not stk_ok

    def test_verification_payment_starts_and_is_blocked_while_pending(self, landlord, prop, stk_ok):
        client = authed(landlord.user)
        url = f"/api/v1/payments/property-verification/{prop.id}/pay/"
        assert client.post(url, {"phone_number": "0722000101"}, format="json").status_code == 202
        again = client.post(url, {"phone_number": "0722000101"}, format="json")
        assert again.status_code == 409 and again.data["error"]["code"] == "payment_pending"
        assert Payment.objects.get().amount == views.VERIFICATION_FEE

    def test_already_verified_property_cannot_be_paid_for(self, landlord, prop, stk_ok):
        prop.verification_status = Property.VerificationStatus.VERIFIED
        prop.save(update_fields=["verification_status"])
        response = authed(landlord.user).post(f"/api/v1/payments/property-verification/{prop.id}/pay/", {"phone_number": "0722000101"}, format="json")
        assert response.status_code == 409 and not stk_ok

    def test_rejected_property_resubmits_without_a_second_charge(self, landlord, prop, stk_ok):
        pending_payment("ws_CO_old", purpose=Payment.Purpose.VERIFICATION_FEE, property=prop, amount=2000, status=Payment.Status.SUCCESSFUL)
        prop.verification_status = Property.VerificationStatus.REJECTED
        prop.save(update_fields=["verification_status"])
        response = authed(landlord.user).post(f"/api/v1/payments/property-verification/{prop.id}/pay/", {"phone_number": "0722000101"}, format="json")
        assert response.status_code == 200 and response.data["status"] == "pending"
        prop.refresh_from_db()
        assert prop.verification_status == Property.VerificationStatus.PENDING
        assert not stk_ok
