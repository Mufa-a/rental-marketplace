from datetime import timedelta
from django.utils import timezone
from .models import ReferralAttribution, ReferralFee

def fee_for_rent(rent):
    if rent < 15_000: return 1_500
    if rent < 30_000: return 2_500
    if rent <= 60_000: return 4_000
    return 6_000

def create_fee_for_rented_viewing(viewing):
    """Create the agreed fee and attribution window from the completed viewing."""
    confirmed_at = viewing.completed_at or timezone.now()
    attribution, _ = ReferralAttribution.objects.get_or_create(
        viewing=viewing,
        defaults={"tenant": viewing.request.tenant, "landlord": viewing.request.unit.property.landlord, "expires_at": confirmed_at + timedelta(days=60), "confirmed_at": confirmed_at},
    )
    return ReferralFee.objects.get_or_create(attribution=attribution, defaults={"amount": fee_for_rent(viewing.request.unit.monthly_rent), "due_at": timezone.now() + timedelta(days=7)})
