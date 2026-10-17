from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.properties.models import Property, Unit
from apps.referrals.models import ReferralFee
from apps.referrals.services import create_fee_for_rented_viewing
from apps.viewings.models import Viewing, ViewingRequest

from .models import Notification


def make_fee(suffix, *, due_in_days, status=ReferralFee.Status.PENDING):
    tenant = TenantProfile.objects.create(user=User.objects.create_user(username=f"t{suffix}", phone_number=f"+25471100{suffix}", role="tenant"))
    landlord = LandlordProfile.objects.create(user=User.objects.create_user(username=f"l{suffix}", phone_number=f"+25472200{suffix}", role="landlord"))
    prop = Property.objects.create(landlord=landlord, name="Home", address_line="1 Road", area="Westlands", city="Nairobi", county="Nairobi")
    unit = Unit.objects.create(property=prop, unit_number="1", title=f"Studio {suffix}", unit_type="studio", monthly_rent=20000)
    request = ViewingRequest.objects.create(tenant=tenant, unit=unit, status=ViewingRequest.Status.APPROVED)
    viewing = Viewing.objects.create(request=request, scheduled_at=timezone.now() - timedelta(days=9), status=Viewing.Status.RENTED)
    fee, _ = create_fee_for_rented_viewing(viewing)
    fee.due_at = timezone.now() + timedelta(days=due_in_days)
    fee.status = status
    fee.save(update_fields=["due_at", "status"])
    return fee, landlord.user


@pytest.mark.django_db
class TestOverdueFeeReminders:
    def test_one_reminder_is_queued_per_overdue_fee_even_if_the_command_runs_repeatedly(self, settings):
        settings.AFRICASTALKING_API_KEY = ""
        fee, landlord_user = make_fee("01", due_in_days=-2)
        call_command("run_notifications", verbosity=0)
        call_command("run_notifications", verbosity=0)
        reminders = Notification.objects.filter(event="referral.fee_overdue")
        assert reminders.count() == 1
        note = reminders.get()
        assert note.recipient_id == landlord_user.id
        assert f"KSh {fee.amount:,}" in note.message and "Studio 01" in note.message

    def test_fees_that_are_paid_waived_or_not_yet_due_get_no_reminder(self, settings):
        settings.AFRICASTALKING_API_KEY = ""
        make_fee("02", due_in_days=-2, status=ReferralFee.Status.PAID)
        make_fee("03", due_in_days=-2, status=ReferralFee.Status.WAIVED)
        make_fee("04", due_in_days=3)
        call_command("run_notifications", verbosity=0)
        assert not Notification.objects.filter(event="referral.fee_overdue").exists()


@pytest.mark.django_db
class TestAdminSeesOverdueFees:
    def _overview(self):
        admin = User.objects.create_superuser(phone_number="+254700000061", password="secure-test-password")
        client = APIClient()
        client.force_authenticate(admin)
        return client.get("/api/v1/admin/overview/").data

    def test_overdue_fees_appear_in_focus_and_metrics(self):
        make_fee("05", due_in_days=-8)
        make_fee("06", due_in_days=4)
        data = self._overview()
        item = next(entry for entry in data["focus"] if entry["key"] == "overdue_fees")
        assert item["count"] == 1 and item["severity"] == "high"
        assert data["metrics"]["fees_overdue"] == 1 and data["metrics"]["fees_due"] == 2

    def test_no_overdue_item_when_everything_is_current(self):
        make_fee("07", due_in_days=4)
        data = self._overview()
        assert not any(entry["key"] == "overdue_fees" for entry in data["focus"])
        assert data["metrics"]["fees_overdue"] == 0
