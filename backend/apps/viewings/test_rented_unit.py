"""What happens around a landlord's "rented" report."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import TenantProfile, User
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.payments.models import ViewingCreditPurchase
from apps.properties.models import Unit
from apps.referrals.models import ReferralFee

from .models import Viewing, ViewingRequest
from .tests import give_credits, marketplace


def second_tenant(phone="+254711000777"):
    user = User.objects.create_user(username=phone, phone_number=phone, role="tenant")
    tenant = TenantProfile.objects.create(user=user)
    give_credits(tenant)
    return user, tenant


def request_viewing(user, unit):
    client = APIClient()
    client.force_authenticate(user)
    response = client.post("/api/v1/viewings/requests/", {"unit": unit.id, "preferred_times": []}, format="json")
    assert response.status_code == 201, response.data
    return ViewingRequest.objects.get(pk=response.data["id"])


def viewing_awaiting_outcome(tenant, unit):
    approved = ViewingRequest.objects.create(tenant=tenant, unit=unit, status=ViewingRequest.Status.APPROVED)
    return Viewing.objects.create(request=approved, scheduled_at=timezone.now() - timedelta(hours=3), status=Viewing.Status.OUTCOME_PENDING)


def report(user, viewing, choice):
    client = APIClient()
    client.force_authenticate(user)
    return client.post(f"/api/v1/viewings/{viewing.id}/outcome/", {"choice": choice}, format="json")


@pytest.mark.django_db
class TestRentedUnitClosesCompetingRequests:
    def test_other_pending_requests_are_rejected_with_credit_returned_and_tenant_told(self):
        _, tenant, landlord_user, unit = marketplace("ru")
        other_user, other_tenant = second_tenant()
        competing = request_viewing(other_user, unit)
        assert ViewingCreditPurchase.objects.get(tenant=other_tenant).credits_remaining == 2

        viewing = viewing_awaiting_outcome(tenant, unit)
        assert report(landlord_user, viewing, "rented").status_code == 201

        competing.refresh_from_db()
        assert competing.status == ViewingRequest.Status.REJECTED
        assert competing.landlord_note == "This home has been rented." and competing.responded_at is not None
        assert ViewingCreditPurchase.objects.get(tenant=other_tenant).credits_remaining == 3
        note = Notification.objects.get(event="viewing.unit_rented")
        assert note.recipient_id == other_user.id and "rented" in note.message
        assert AuditLog.objects.filter(action="viewing_request.closed_unit_rented", object_id=str(competing.pk)).exists()

    def test_requests_for_other_units_and_already_approved_requests_are_left_alone(self):
        _, tenant, landlord_user, unit = marketplace("ro")
        elsewhere = Unit.objects.create(property=unit.property, unit_number="Z9", title="Other", unit_type="studio", monthly_rent=9000, is_published=True)
        other_user, other_tenant = second_tenant()
        pending_elsewhere = request_viewing(other_user, elsewhere)
        approved_here = ViewingRequest.objects.create(tenant=other_tenant, unit=unit, status=ViewingRequest.Status.APPROVED)

        viewing = viewing_awaiting_outcome(tenant, unit)
        assert report(landlord_user, viewing, "rented").status_code == 201

        pending_elsewhere.refresh_from_db(); approved_here.refresh_from_db()
        assert pending_elsewhere.status == ViewingRequest.Status.PENDING
        assert approved_here.status == ViewingRequest.Status.APPROVED
        assert not Notification.objects.filter(event="viewing.unit_rented").exists()

    def test_the_rented_request_itself_is_not_rejected(self):
        _, tenant, landlord_user, unit = marketplace("rs")
        viewing = viewing_awaiting_outcome(tenant, unit)
        report(landlord_user, viewing, "rented")
        viewing.request.refresh_from_db()
        assert viewing.request.status == ViewingRequest.Status.APPROVED

    def test_a_non_rental_outcome_does_not_close_other_requests(self):
        _, tenant, landlord_user, unit = marketplace("rn")
        other_user, _ = second_tenant()
        competing = request_viewing(other_user, unit)
        viewing = viewing_awaiting_outcome(tenant, unit)
        report(landlord_user, viewing, "did_not_rent")
        competing.refresh_from_db()
        assert competing.status == ViewingRequest.Status.PENDING


@pytest.mark.django_db
class TestLandlordRentedReportIsFinal:
    """Documents the rule the README describes: the landlord's report alone triggers the fee."""

    def test_landlord_report_alone_creates_the_fee_and_takes_the_unit_off_the_market(self):
        _, tenant, landlord_user, unit = marketplace("lf")
        viewing = viewing_awaiting_outcome(tenant, unit)
        assert report(landlord_user, viewing, "rented").status_code == 201
        viewing.refresh_from_db(); unit.refresh_from_db()
        assert viewing.status == Viewing.Status.RENTED
        assert ReferralFee.objects.filter(attribution__viewing=viewing, status=ReferralFee.Status.PENDING).exists()
        assert unit.available is False and unit.is_published is False

    def test_landlord_rented_report_takes_precedence_over_a_earlier_tenant_report(self):
        tenant_user, tenant, landlord_user, unit = marketplace("lp")
        viewing = viewing_awaiting_outcome(tenant, unit)
        assert report(tenant_user, viewing, "did_not_rent").status_code == 201
        assert report(landlord_user, viewing, "rented").status_code == 201
        viewing.refresh_from_db()
        assert viewing.status == Viewing.Status.RENTED
        assert ReferralFee.objects.filter(attribution__viewing=viewing).count() == 1

    def test_the_report_cannot_be_changed_afterwards(self):
        _, tenant, landlord_user, unit = marketplace("lc")
        viewing = viewing_awaiting_outcome(tenant, unit)
        report(landlord_user, viewing, "rented")
        again = report(landlord_user, viewing, "did_not_rent")
        assert again.status_code == 400
        viewing.refresh_from_db()
        assert viewing.status == Viewing.Status.RENTED
