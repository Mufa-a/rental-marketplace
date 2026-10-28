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


def _approve(client, landlord_user, request_id, hours=2):
    client.force_authenticate(landlord_user)
    response = client.post(f"/api/v1/viewings/requests/{request_id}/approve/",
                           {"scheduled_at": (timezone.now() + timedelta(hours=hours)).isoformat(), "meeting_note": "Gate B"}, format="json")
    assert response.status_code == 201, response.data
    return Viewing.objects.get(request_id=request_id)


def _past(viewing, days=1):
    Viewing.objects.filter(pk=viewing.pk).update(scheduled_at=timezone.now() - timedelta(days=days))
    viewing.refresh_from_db()
    return viewing


@pytest.mark.django_db
class TestBookingWorkflow:
    def _request(self, client, unit):
        response = client.post("/api/v1/viewings/requests/", {"unit": unit.id}, format="json")
        assert response.status_code == 201, response.data
        return response.data["id"]

    def test_duplicate_request_for_the_same_home_is_refused_without_spending_a_credit(self):
        """Regression: each duplicate request used to reserve another paid credit."""
        tenant_user, tenant, _, unit = marketplace("dup")
        client = APIClient(); client.force_authenticate(tenant_user)
        self._request(client, unit)
        second = client.post("/api/v1/viewings/requests/", {"unit": unit.id}, format="json")
        assert second.status_code == 409 and second.data["error"]["code"] == "duplicate_request"
        assert ViewingCreditPurchase.objects.get(tenant=tenant).credits_remaining == 2

    def test_dashboard_reads_are_not_rate_limited(self):
        """Regression: the 20/hour request-creation limit also applied to GET, emptying dashboards."""
        _, _, landlord_user, _ = marketplace("rl")
        client = APIClient(); client.force_authenticate(landlord_user)
        assert {client.get("/api/v1/viewings/requests/").status_code for _ in range(25)} == {200}

    def test_validation_messages_reach_the_client(self):
        tenant_user, _, _, unit = marketplace("vm")
        unit.available = False; unit.save()
        client = APIClient(); client.force_authenticate(tenant_user)
        response = client.post("/api/v1/viewings/requests/", {"unit": unit.id}, format="json")
        assert response.status_code == 400
        assert "not open for viewings" in response.data["error"]["message"]

    def test_unmoderated_or_held_homes_cannot_be_requested(self):
        tenant_user, _, _, unit = marketplace("mod")
        client = APIClient(); client.force_authenticate(tenant_user)
        unit.moderation_status = "pending_review"; unit.save()
        assert client.post("/api/v1/viewings/requests/", {"unit": unit.id}, format="json").status_code == 400
        unit.moderation_status = "approved"; unit.moderation_hold = True; unit.save()
        assert client.post("/api/v1/viewings/requests/", {"unit": unit.id}, format="json").status_code == 400

    def test_contact_details_are_released_only_after_approval_and_only_to_the_parties(self):
        tenant_user, _, landlord_user, unit = marketplace("ct")
        landlord_user.first_name = "Wanjiru"; landlord_user.save()
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        assert client.get(f"/api/v1/viewings/requests/{request_id}/").data["contact"] is None
        client.force_authenticate(landlord_user)
        assert client.get(f"/api/v1/viewings/requests/{request_id}/").data["contact"] is None

        _approve(client, landlord_user, request_id)
        client.force_authenticate(tenant_user)
        contact = client.get(f"/api/v1/viewings/requests/{request_id}/").data["contact"]
        assert contact["address"] == "1 Test" and contact["phone"] == landlord_user.phone_number
        assert contact["name"] == "Wanjiru" and contact["meeting_note"] == "Gate B"
        client.force_authenticate(landlord_user)
        assert client.get(f"/api/v1/viewings/requests/{request_id}/").data["contact"]["phone"] == tenant_user.phone_number

        outsider, _, _, _ = marketplace("ct2")
        client.force_authenticate(outsider)
        assert client.get(f"/api/v1/viewings/requests/{request_id}/").status_code == 404
        # Public listing never exposes the street address.
        assert "address_line" not in str(APIClient().get(f"/api/v1/properties/listings/{unit.slug}/").data)

    def test_landlord_cancelling_an_approved_viewing_returns_the_consumed_credit(self):
        tenant_user, tenant, landlord_user, unit = marketplace("lc")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        _approve(client, landlord_user, request_id)
        assert ViewingCreditPurchase.objects.get(tenant=tenant).credits_remaining == 2
        response = client.post(f"/api/v1/viewings/requests/{request_id}/cancel/", {"reason": "Plumbing repairs"}, format="json")
        assert response.status_code == 200 and response.data["cancelled_by"] == "landlord"
        assert ViewingCreditPurchase.objects.get(tenant=tenant).credits_remaining == 3
        assert tenant_user.notifications.filter(event="viewing.cancelled", channel="in_app").exists()

    def test_tenant_cancelling_an_approved_viewing_uses_the_credit(self):
        tenant_user, tenant, landlord_user, unit = marketplace("tc")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        _approve(client, landlord_user, request_id)
        client.force_authenticate(tenant_user)
        assert client.post(f"/api/v1/viewings/requests/{request_id}/cancel/", {}, format="json").status_code == 200
        assert ViewingCreditPurchase.objects.get(tenant=tenant).credits_remaining == 2

    def test_reschedule_is_limited_and_notifies_the_tenant(self):
        tenant_user, _, landlord_user, unit = marketplace("rs")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        viewing = _approve(client, landlord_user, request_id)
        for _ in range(3):
            when = (timezone.now() + timedelta(days=2)).isoformat()
            assert client.post(f"/api/v1/viewings/{viewing.id}/reschedule/", {"scheduled_at": when}, format="json").status_code == 200
        assert client.post(f"/api/v1/viewings/{viewing.id}/reschedule/", {"scheduled_at": when}, format="json").status_code == 400
        assert tenant_user.notifications.filter(event="viewing.rescheduled", channel="in_app").count() == 3
        client.force_authenticate(tenant_user)
        assert client.post(f"/api/v1/viewings/{viewing.id}/reschedule/", {"scheduled_at": when}, format="json").status_code == 403

    def test_viewings_cannot_be_scheduled_far_ahead_or_completed_early(self):
        tenant_user, _, landlord_user, unit = marketplace("fa")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        client.force_authenticate(landlord_user)
        far = (timezone.now() + timedelta(days=90)).isoformat()
        assert client.post(f"/api/v1/viewings/requests/{request_id}/approve/", {"scheduled_at": far}, format="json").status_code == 400
        viewing = _approve(client, landlord_user, request_id, hours=48)
        assert client.post(f"/api/v1/viewings/{viewing.id}/complete/", {}, format="json").status_code == 400

    def test_timeline_records_each_step_by_role(self):
        tenant_user, _, landlord_user, unit = marketplace("tl")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = self._request(client, unit)
        viewing = _past(_approve(client, landlord_user, request_id))
        client.force_authenticate(tenant_user)
        client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "did_not_rent"}, format="json")
        events = client.get(f"/api/v1/viewings/requests/{request_id}/").data["timeline"]
        assert [(e["action"], e["by"]) for e in events] == [
            ("viewing_request.created", "tenant"), ("viewing.scheduled", "landlord"), ("viewing.outcome_reported", "tenant")]


@pytest.mark.django_db
class TestReferralProtection:
    def _viewed(self, suffix):
        tenant_user, tenant, landlord_user, unit = marketplace(suffix)
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = client.post("/api/v1/viewings/requests/", {"unit": unit.id}, format="json").data["id"]
        viewing = _past(_approve(client, landlord_user, request_id))
        return client, tenant_user, landlord_user, unit, viewing

    def test_tenant_rental_report_asks_the_landlord_to_confirm(self):
        from apps.referrals.models import ReferralFee, ReferralFlag
        client, tenant_user, landlord_user, unit, viewing = self._viewed("tr")
        client.force_authenticate(tenant_user)
        assert client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "rented"}, format="json").status_code == 201
        assert ReferralFlag.objects.filter(viewing=viewing, reason="tenant_reported_rented", status="open").exists()
        assert landlord_user.notifications.filter(event="referral.confirm_requested").exists()
        assert not ReferralFee.objects.exists()

    def test_conflicting_reports_open_a_dispute_and_a_flag(self):
        from apps.referrals.models import ReferralFlag
        from apps.trust.models import Dispute
        client, tenant_user, landlord_user, unit, viewing = self._viewed("cf")
        client.force_authenticate(tenant_user)
        client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "rented"}, format="json")
        client.force_authenticate(landlord_user)
        client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "did_not_rent"}, format="json")
        viewing.refresh_from_db()
        assert viewing.status == Viewing.Status.DISPUTED
        assert Dispute.objects.filter(viewing=viewing).exists()
        assert ReferralFlag.objects.filter(viewing=viewing, reason="outcome_conflict").exists()

    def test_landlord_rental_report_creates_one_fee_and_takes_the_unit_off_the_market(self, monkeypatch):
        from apps.referrals import services as referral_services
        from apps.referrals.models import ReferralFee
        monkeypatch.setattr(referral_services, "request_fee_payment", lambda fee, actor: None)
        client, _, landlord_user, unit, viewing = self._viewed("lr")
        client.force_authenticate(landlord_user)
        response = client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "rented"}, format="json")
        assert response.status_code == 201
        assert response.data["fee"]["amount"] == 1500  # rent 12,000 falls in the lowest seeded band
        assert client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "rented"}, format="json").status_code == 400
        unit.refresh_from_db()
        assert ReferralFee.objects.count() == 1 and not unit.available and not unit.is_published
        assert APIClient().get(f"/api/v1/properties/listings/{unit.slug}/").status_code == 404

    def test_marking_a_unit_occupied_after_a_viewing_asks_the_tenant(self):
        from apps.referrals.models import ReferralFlag
        client, tenant_user, landlord_user, unit, viewing = self._viewed("oc")
        client.force_authenticate(landlord_user)
        assert client.post(f"/api/v1/properties/units/{unit.id}/availability/", {"available": False}, format="json").status_code == 200
        assert ReferralFlag.objects.filter(viewing=viewing, reason="occupied_after_viewing", status="open").count() == 1
        assert tenant_user.notifications.filter(event="referral.confirm_requested", channel="in_app").exists()
        # Toggling again does not spam the tenant or duplicate the flag.
        client.post(f"/api/v1/properties/units/{unit.id}/availability/", {"available": True}, format="json")
        client.post(f"/api/v1/properties/units/{unit.id}/availability/", {"available": False}, format="json")
        assert ReferralFlag.objects.filter(viewing=viewing, reason="occupied_after_viewing").count() == 1

    def test_a_late_rental_report_is_accepted_inside_the_attribution_window(self):
        client, tenant_user, landlord_user, unit, viewing = self._viewed("late")
        for user in (tenant_user, landlord_user):
            client.force_authenticate(user)
            client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "did_not_rent"}, format="json")
        viewing.refresh_from_db()
        assert viewing.status == Viewing.Status.DID_NOT_RENT
        client.force_authenticate(tenant_user)
        assert client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "rented"}, format="json").status_code == 200
        viewing.refresh_from_db()
        assert viewing.status == Viewing.Status.DISPUTED

    def test_admin_ruling_creates_the_fee_and_resolves_the_dispute(self):
        from apps.referrals.models import ReferralFee, ReferralFlag
        from apps.referrals.services import resolve_flag_or_dispute
        from apps.trust.models import Dispute
        client, tenant_user, landlord_user, unit, viewing = self._viewed("ar")
        client.force_authenticate(tenant_user)
        client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "rented"}, format="json")
        client.force_authenticate(landlord_user)
        client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "did_not_rent"}, format="json")
        admin = User.objects.create_superuser(phone_number="+254700000777", password="x-secure-password")
        fee = resolve_flag_or_dispute(viewing, admin=admin, rented=True, note="Tenant showed signed lease")
        viewing.refresh_from_db()
        assert viewing.status == Viewing.Status.RENTED and fee.source == ReferralFee.Source.ADMIN_RULING
        assert Dispute.objects.get(viewing=viewing).status == Dispute.Status.RESOLVED
        assert not ReferralFlag.objects.filter(viewing=viewing, status="open").exists()
        assert AuditLog.objects.filter(action="referral.ruling", actor=admin).exists()


@pytest.mark.django_db
def test_a_viewing_that_has_happened_cannot_be_cancelled_or_moved_to_dodge_attribution():
    tenant_user, tenant, landlord_user, unit = marketplace("dodge")
    client = APIClient(); client.force_authenticate(tenant_user)
    request_id = client.post("/api/v1/viewings/requests/", {"unit": unit.id}, format="json").data["id"]
    viewing = _past(_approve(client, landlord_user, request_id), days=0.1)
    client.force_authenticate(landlord_user)
    assert client.post(f"/api/v1/viewings/requests/{request_id}/cancel/", {}, format="json").status_code == 400
    future = (timezone.now() + timedelta(days=1)).isoformat()
    assert client.post(f"/api/v1/viewings/{viewing.id}/reschedule/", {"scheduled_at": future}, format="json").status_code == 400
    assert client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": "no_show"}, format="json").status_code == 201
