from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import AuditLog
from apps.notifications.services import notify

from .models import ReferralAttribution, ReferralFee, ReferralFlag


def _audit(actor, action, obj, **metadata):
    AuditLog.objects.create(actor=actor, action=action, object_type=obj._meta.label, object_id=str(obj.pk), metadata=metadata)


def fee_for_rent(rent, country=None):
    from apps.payments.services import referral_fee_for
    return referral_fee_for(rent, country)


def create_fee_for_rented_viewing(viewing, *, source=ReferralFee.Source.LANDLORD_REPORT):
    """Create the attribution and fee for a viewing that became a tenancy. Idempotent."""
    unit = viewing.request.unit
    confirmed_at = viewing.completed_at or timezone.now()
    attribution, _ = ReferralAttribution.objects.get_or_create(
        viewing=viewing,
        defaults={"tenant": viewing.request.tenant, "landlord": unit.property.landlord,
                  "expires_at": confirmed_at + timedelta(days=settings.REFERRAL_ATTRIBUTION_DAYS), "confirmed_at": confirmed_at},
    )
    return ReferralFee.objects.get_or_create(attribution=attribution, defaults={
        "amount": fee_for_rent(unit.monthly_rent, unit.property.country), "monthly_rent": unit.monthly_rent, "source": source,
        "due_at": timezone.now() + timedelta(days=settings.REFERRAL_FEE_DUE_DAYS),
    })


def mark_unit_occupied(unit):
    unit.available = False
    unit.is_published = False
    unit.availability_confirmed_at = timezone.now()
    unit.save(update_fields=["available", "is_published", "availability_confirmed_at", "updated_at"])
    from apps.properties.views import _invalidate_public_listing_cache
    transaction.on_commit(_invalidate_public_listing_cache)


def request_fee_payment(fee, actor):
    """Send the landlord an STK prompt for a new fee. Never raises: the fee stays payable from the dashboard."""
    from apps.payments.models import Payment
    from apps.payments.services import MpesaError, start_payment

    landlord_user = fee.attribution.landlord.user
    try:
        payment, _ = start_payment(
            actor=actor, purpose=Payment.Purpose.REFERRAL_FEE, amount=fee.amount, phone=landlord_user.phone_number,
            idempotency_key=f"referral-auto:{fee.pk}", reference="NYF{id}", description="Success fee", fee=fee,
        )
    except MpesaError:
        return None
    return payment


def finalize_rental(viewing, *, actor, source):
    """Record a confirmed tenancy: viewing RENTED, fee owed, unit off the market, parties told."""
    from apps.viewings.models import Viewing

    viewing.status = Viewing.Status.RENTED
    viewing.save(update_fields=["status", "updated_at"])
    fee, created = create_fee_for_rented_viewing(viewing, source=source)
    unit = viewing.request.unit
    if unit.available or unit.is_published:
        mark_unit_occupied(unit)
    ReferralFlag.objects.filter(viewing=viewing, status=ReferralFlag.Status.OPEN).update(
        status=ReferralFlag.Status.CONFIRMED_RENTED, resolved_at=timezone.now(), resolved_by=actor if source == ReferralFee.Source.ADMIN_RULING else None,
        resolution_note="Rental confirmed.",
    )
    if created:
        _audit(actor, "referral.fee_created", fee, viewing_id=viewing.pk, amount=fee.amount, source=source)
        landlord_user = unit.property.landlord.user
        notify(recipient=landlord_user, event="referral.fee_created", dedupe_key=f"referral-fee:{fee.pk}:landlord",
               title="Success fee due",
               message=f"{unit.title} was rented through a Nyumbani viewing. A {fee.currency} {fee.amount:,} success fee is due by "
                       f"{timezone.localtime(fee.due_at).strftime('%d %b %Y')}. Pay from the Payments tab of your dashboard.",
               link="/landlord?tab=payments")
        notify(recipient=viewing.request.tenant.user, event="referral.rental_recorded", dedupe_key=f"referral-fee:{fee.pk}:tenant",
               title="Rental recorded", message=f"Congratulations on your new home at {unit.title}. The listing is now marked as let.",
               link="/tenant")
    return fee, created


def raise_flag(viewing, reason, *, detail=""):
    """Open a review flag once per viewing and reason."""
    if ReferralFlag.objects.filter(viewing=viewing, reason=reason, status=ReferralFlag.Status.OPEN).exists():
        return None
    try:
        with transaction.atomic():
            flag = ReferralFlag.objects.create(viewing=viewing, reason=reason, detail=detail[:255])
    except IntegrityError:
        return None
    _audit(None, "referral.flag_opened", flag, viewing_id=viewing.pk, reason=reason)
    return flag


def recent_viewings_without_rental(unit):
    """Viewings of this unit inside the attribution window that have happened but have no recorded rental."""
    from apps.viewings.models import Viewing

    window_start = timezone.now() - timedelta(days=settings.REFERRAL_ATTRIBUTION_DAYS)
    return (Viewing.objects.filter(request__unit=unit, scheduled_at__gte=window_start, scheduled_at__lte=timezone.now())
            .exclude(status__in=[Viewing.Status.CANCELLED, Viewing.Status.RENTED, Viewing.Status.NO_SHOW])
            .exclude(attribution__isnull=False)
            .select_related("request__tenant__user", "request__unit"))


def on_unit_marked_occupied(unit, actor):
    """The landlord took a unit off the market. Ask recent viewers whether they rented it.

    This is the main anti-bypass check: it uses only what happened on the platform, and
    the tenant can simply answer "no".
    """
    for viewing in recent_viewings_without_rental(unit):
        flag = raise_flag(viewing, ReferralFlag.Reason.UNIT_OCCUPIED_AFTER_VIEWING,
                          detail=f"Unit marked occupied on {timezone.localdate():%d %b %Y}.")
        if flag:
            notify(recipient=viewing.request.tenant.user, event="referral.confirm_requested",
                   dedupe_key=f"referral-flag:{flag.pk}:tenant", title="Did you rent this home?",
                   message=f"{unit.title}, which you viewed, is now marked as let. If you rented it, please confirm on your dashboard. "
                           "If not, tell us so we can keep records accurate.",
                   link="/tenant")


@transaction.atomic
def resolve_flag_or_dispute(viewing, *, admin, rented, note=""):
    """Administrator ruling on whether a viewing converted to a tenancy."""
    from apps.trust.models import Dispute
    from apps.viewings.models import Viewing

    viewing = Viewing.objects.select_for_update().select_related("request__unit__property__landlord__user", "request__tenant__user").get(pk=viewing.pk)
    now = timezone.now()
    if rented:
        fee, _ = finalize_rental(viewing, actor=admin, source=ReferralFee.Source.ADMIN_RULING)
    else:
        fee = None
        if viewing.status in (Viewing.Status.DISPUTED, Viewing.Status.OUTCOME_PENDING, Viewing.Status.STILL_DECIDING, Viewing.Status.SCHEDULED):
            viewing.status = Viewing.Status.DID_NOT_RENT
            viewing.save(update_fields=["status", "updated_at"])
        ReferralFlag.objects.filter(viewing=viewing, status=ReferralFlag.Status.OPEN).update(
            status=ReferralFlag.Status.DISMISSED, resolved_at=now, resolved_by=admin, resolution_note=note[:500])
    Dispute.objects.filter(viewing=viewing, status=Dispute.Status.PENDING).update(
        status=Dispute.Status.RESOLVED, ruling=(note or ("Rental confirmed." if rented else "No rental found."))[:2000])
    _audit(admin, "referral.ruling", viewing, rented=rented, note=note[:200], fee_id=fee.pk if fee else None)
    for user, role in ((viewing.request.tenant.user, "tenant"), (viewing.request.unit.property.landlord.user, "landlord")):
        notify(recipient=user, event="referral.ruling", dedupe_key=f"viewing:{viewing.pk}:ruling:{now.timestamp()}:{role}",
               title="Viewing outcome reviewed",
               message=f"Our team reviewed the outcome of the viewing for {viewing.request.unit.title}: "
                       f"{'recorded as rented' if rented else 'recorded as not rented'}.",
               link="/landlord?tab=viewings" if role == "landlord" else "/tenant")
    return fee
