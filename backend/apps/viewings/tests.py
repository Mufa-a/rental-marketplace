import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.properties.models import Property, Unit
from apps.core.models import AuditLog
from apps.payments.models import Payment, ViewingCreditPurchase
from apps.viewings.models import Viewing, ViewingRequest


def give_credits(tenant, credits=3):
    """A successful bundle purchase, as the M-Pesa callback would create it."""
    payment = Payment.objects.create(
        purpose=Payment.Purpose.VIEWING_CREDITS, tenant_user=tenant.user, credits=credits, amount=100,
        phone_number=tenant.user.phone_number, provider_reference=f"test-{tenant.pk}", idempotency_key=f"key-{tenant.pk}",
        status=Payment.Status.SUCCESSFUL,
    )
    return ViewingCreditPurchase.objects.create(payment=payment, tenant=tenant, credits_total=credits, credits_remaining=credits)


def marketplace(suffix="a"):
    tenant_user = User.objects.create_user(username=f"tenant-{suffix}", phone_number=f"+2547111{suffix:0>5}", role="tenant")
    tenant = TenantProfile.objects.create(user=tenant_user)
    landlord_user = User.objects.create_user(username=f"landlord-{suffix}", phone_number=f"+2547222{suffix:0>5}", role="landlord")
    landlord = LandlordProfile.objects.create(user=landlord_user)
    prop = Property.objects.create(landlord=landlord, name="Test", address_line="1 Test", area="Westlands", city="Nairobi", county="Nairobi")
    unit = Unit.objects.create(property=prop, unit_number="A1", title="Studio", unit_type="studio", monthly_rent=12000, is_published=True)
    give_credits(tenant)
    return tenant_user, tenant, landlord_user, unit

@pytest.mark.django_db
def test_tenant_request_landlord_approval_and_completion():
    tenant_user, tenant, landlord_user, unit = marketplace("v")
    client = APIClient(); client.force_authenticate(tenant_user)
    response = client.post("/api/v1/viewings/requests/", {"unit": unit.id, "preferred_times": []}, format="json")
    assert response.status_code == 201
    request = ViewingRequest.objects.get(tenant=tenant)
    client.force_authenticate(landlord_user)
    response = client.post(f"/api/v1/viewings/requests/{request.id}/approve/", {"scheduled_at": (timezone.now() + timedelta(hours=1)).isoformat()}, format="json")
    assert response.status_code == 201
    viewing = Viewing.objects.get(request=request)
    client.force_authenticate(tenant_user)
    response = client.post(f"/api/v1/viewings/{viewing.id}/complete/", {}, format="json")
    assert response.status_code == 200
    assert response.data["status"] == "outcome_pending"


@pytest.mark.django_db
def test_both_parties_can_confirm_rental_before_fee_is_created():
    from apps.referrals.models import ReferralFee

    tenant_user = User.objects.create_user(username="tenant-outcome", phone_number="+254711111112", role="tenant")
    tenant = TenantProfile.objects.create(user=tenant_user)
    landlord_user = User.objects.create_user(username="landlord-outcome", phone_number="+254722222223", role="landlord")
    landlord = LandlordProfile.objects.create(user=landlord_user)
    property = Property.objects.create(landlord=landlord, name="Test", address_line="1 Test", area="Westlands", city="Nairobi", county="Nairobi")
    unit = Unit.objects.create(property=property, unit_number="B1", title="Studio", unit_type="studio", monthly_rent=12000, is_published=True)
    viewing_request = ViewingRequest.objects.create(tenant=tenant, unit=unit, status=ViewingRequest.Status.APPROVED)
    viewing = Viewing.objects.create(request=viewing_request, scheduled_at=timezone.now() + timedelta(hours=1), status=Viewing.Status.OUTCOME_PENDING)

    client = APIClient()
    client.force_authenticate(tenant_user)
    first = client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "rented"}, format="json")
    assert first.status_code == 201
    viewing.refresh_from_db()
    assert viewing.status == Viewing.Status.OUTCOME_PENDING

    client.force_authenticate(landlord_user)
    second = client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "rented"}, format="json")
    assert second.status_code == 201
    viewing.refresh_from_db()
    unit.refresh_from_db()
    assert viewing.status == Viewing.Status.RENTED
    assert unit.available is False
    assert ReferralFee.objects.filter(attribution__viewing=viewing).exists()



@pytest.mark.django_db
class TestViewingAccessControlAndAudit:
    def _request(self, client, unit):
        response = client.post("/api/v1/viewings/requests/", {"unit": unit.id, "preferred_times": []}, format="json")
        assert response.status_code == 201, response.data
        return response.data["id"]

    def test_request_requires_a_bundle(self):
        tenant_user, tenant, _, unit = marketplace("nb")
        ViewingCreditPurchase.objects.filter(tenant=tenant).delete()
        client = APIClient(); client.force_authenticate(tenant_user)
        assert client.post("/api/v1/viewings/requests/", {"unit": unit.id}, format="json").status_code == 400

    def test_other_tenant_cannot_see_or_cancel_a_request(self):
        tenant_user, _, _, unit = marketplace("t1")
        other_user, _, _, _ = marketplace("t2")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        client.force_authenticate(other_user)
        assert client.get("/api/v1/viewings/requests/").data == []
        assert client.post(f"/api/v1/viewings/requests/{request_id}/cancel/", {}, format="json").status_code == 403
        assert ViewingRequest.objects.get(pk=request_id).status == "pending_landlord"

    def test_other_landlord_cannot_approve_or_reject(self):
        tenant_user, _, _, unit = marketplace("l1")
        _, _, stranger, _ = marketplace("l2")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        client.force_authenticate(stranger)
        when = (timezone.now() + timedelta(days=1)).isoformat()
        assert client.post(f"/api/v1/viewings/requests/{request_id}/approve/", {"scheduled_at": when}, format="json").status_code == 403
        assert client.post(f"/api/v1/viewings/requests/{request_id}/reject/", {}, format="json").status_code == 403
        assert client.get("/api/v1/viewings/requests/").data == []

    def test_tenant_cannot_approve_own_request(self):
        tenant_user, _, _, unit = marketplace("s1")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        when = (timezone.now() + timedelta(days=1)).isoformat()
        assert client.post(f"/api/v1/viewings/requests/{request_id}/approve/", {"scheduled_at": when}, format="json").status_code == 403

    def test_uninvolved_user_cannot_touch_a_viewing(self):
        tenant_user, tenant, landlord_user, unit = marketplace("v1")
        outsider, _, _, _ = marketplace("v2")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        client.force_authenticate(landlord_user)
        client.post(f"/api/v1/viewings/requests/{request_id}/approve/", {"scheduled_at": (timezone.now() + timedelta(hours=2)).isoformat()}, format="json")
        viewing = Viewing.objects.get(request_id=request_id)
        client.force_authenticate(outsider)
        assert client.post(f"/api/v1/viewings/{viewing.id}/complete/", {}, format="json").status_code == 403
        assert client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "rented"}, format="json").status_code == 403

    def test_landlord_rejection_restores_credit_records_response_time_and_audit(self):
        tenant_user, tenant, landlord_user, unit = marketplace("r1")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        assert ViewingCreditPurchase.objects.get(tenant=tenant).credits_remaining == 2
        client.force_authenticate(landlord_user)
        response = client.post(f"/api/v1/viewings/requests/{request_id}/reject/", {"note": "Already let"}, format="json")
        assert response.status_code == 200
        item = ViewingRequest.objects.get(pk=request_id)
        assert item.status == "rejected" and item.responded_at is not None
        assert ViewingCreditPurchase.objects.get(tenant=tenant).credits_remaining == 3
        entry = AuditLog.objects.get(action="viewing_request.rejected")
        assert entry.actor_id == landlord_user.id
        assert entry.metadata["from"] == "pending_landlord" and entry.metadata["to"] == "rejected"

    def test_approval_records_response_time_and_scheduling_audit(self):
        tenant_user, _, landlord_user, unit = marketplace("ap")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        client.force_authenticate(landlord_user)
        assert client.post(f"/api/v1/viewings/requests/{request_id}/approve/", {"scheduled_at": (timezone.now() + timedelta(days=1)).isoformat()}, format="json").status_code == 201
        assert ViewingRequest.objects.get(pk=request_id).responded_at is not None
        assert AuditLog.objects.filter(action="viewing.scheduled", metadata__to="approved").exists()

    def test_request_cannot_be_approved_twice(self):
        tenant_user, _, landlord_user, unit = marketplace("tw")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        client.force_authenticate(landlord_user)
        payload = {"scheduled_at": (timezone.now() + timedelta(days=1)).isoformat()}
        assert client.post(f"/api/v1/viewings/requests/{request_id}/approve/", payload, format="json").status_code == 201
        assert client.post(f"/api/v1/viewings/requests/{request_id}/approve/", payload, format="json").status_code == 400
        assert Viewing.objects.filter(request_id=request_id).count() == 1
