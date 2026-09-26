from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.properties.models import Property, Unit
from apps.viewings.models import Viewing, ViewingRequest
from .models import Notification


@pytest.mark.django_db
def test_viewing_reminder_command_deduplicates_for_both_parties(settings):
    tenant_user = User.objects.create_user(phone_number="+254711000001", role=User.Role.TENANT)
    tenant = TenantProfile.objects.create(user=tenant_user)
    landlord_user = User.objects.create_user(phone_number="+254722000001", role=User.Role.LANDLORD)
    landlord = LandlordProfile.objects.create(user=landlord_user)
    property = Property.objects.create(landlord=landlord, name="Home", address_line="1 Road", area="Westlands", city="Nairobi", county="Nairobi")
    unit = Unit.objects.create(property=property, unit_number="1", title="Studio", unit_type="studio", monthly_rent=10000)
    viewing_request = ViewingRequest.objects.create(tenant=tenant, unit=unit, status=ViewingRequest.Status.APPROVED)
    Viewing.objects.create(request=viewing_request, scheduled_at=timezone.now() + timedelta(hours=2))

    settings.AFRICASTALKING_API_KEY = ""
    call_command("run_notifications", verbosity=0)
    call_command("run_notifications", verbosity=0)

    assert Notification.objects.count() == 2
    assert Notification.objects.filter(status=Notification.Status.PENDING).count() == 2
