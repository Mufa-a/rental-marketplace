import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.properties.models import Property, Unit
from apps.viewings.models import Viewing, ViewingRequest

@pytest.mark.django_db
def test_tenant_request_landlord_approval_and_completion():
    tenant_user = User.objects.create_user(username="tenant-v", phone_number="+254711111111", role="tenant")
    tenant = TenantProfile.objects.create(user=tenant_user)
    landlord_user = User.objects.create_user(username="landlord-v", phone_number="+254722222222", role="landlord")
    landlord = LandlordProfile.objects.create(user=landlord_user)
    property = Property.objects.create(landlord=landlord, name="Test", address_line="1 Test", area="Westlands", city="Nairobi", county="Nairobi")
    unit = Unit.objects.create(property=property, unit_number="A1", title="Studio", unit_type="studio", monthly_rent=12000, is_published=True)
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
