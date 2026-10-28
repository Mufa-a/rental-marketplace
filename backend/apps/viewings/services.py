"""The viewing workflow. Every state change goes through here, is audited, and notifies the other party.

    request (credit reserved) ──approve──▶ approved + Viewing scheduled (credit consumed)
        │ reject / tenant cancel / expiry          │ landlord cancel → credit returned
        ▼ (credit returned)                        ▼ complete → outcome reports → rented / not rented / disputed

Contact details and the exact address are released only once a landlord approves a
viewing, so every in-person meeting has an auditable platform record behind it.
"""
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import TenantProfile, User
from apps.core.exceptions import Conflict
from apps.core.models import AuditLog
from apps.core.permissions import is_platform_admin
from apps.notifications.services import notify
from apps.payments.services import reserve_viewing_credit, settle_viewing_credit
from apps.referrals.models import ReferralFee, ReferralFlag
from apps.referrals.services import finalize_rental, raise_flag
from apps.trust.models import Dispute

from .models import Outcome, Viewing, ViewingRequest

MAX_ACTIVE_REQUESTS = 3
MAX_RESCHEDULES = 3
MAX_DAYS_AHEAD = 60
PENDING_EXPIRY_DAYS = 7
OUTCOME_DUE_STATUSES = (Viewing.Status.OUTCOME_PENDING, Viewing.Status.STILL_DECIDING)


def audit(actor, action, obj, **metadata):
    AuditLog.objects.create(actor=actor, action=action, object_type=obj._meta.label, object_id=str(obj.pk), metadata=metadata)


def _when(dt):
    return timezone.localtime(dt).strftime("%a %d %b, %I:%M %p")


def is_landlord_for(user, viewing_request):
    return viewing_request.unit.property.landlord.user_id == user.id


def party_for(user, viewing_request):
    if viewing_request.tenant.user_id == user.id:
        return ViewingRequest.Party.TENANT
    if is_landlord_for(user, viewing_request):
        return ViewingRequest.Party.LANDLORD
    if is_platform_admin(user):
        return ViewingRequest.Party.ADMIN
    return None


def bookable_problem(unit):
    """Why a unit cannot take viewing requests right now, or None."""
    from apps.properties.models import Unit

    cutoff = timezone.now() - timedelta(days=settings.AVAILABILITY_CONFIRMATION_DAYS)
    if not (unit.available and unit.is_published and unit.property.is_active and not unit.moderation_hold
            and unit.moderation_status == Unit.ModerationStatus.APPROVED):
        return "This home is not open for viewings right now."
    if not unit.availability_confirmed_at or unit.availability_confirmed_at < cutoff:
        return "The landlord has not recently confirmed this home is available, so viewings are paused."
    if not unit.property.landlord.user.is_active:
        return "This landlord is not accepting viewings right now."
    return None


@transaction.atomic
def create_request(user, unit, *, note="", preferred_times=None):
    if user.role != User.Role.TENANT:
        raise PermissionDenied("Only tenant accounts can request viewings.")
    tenant = TenantProfile.objects.get_or_create(user=user)[0]
    # Serialise this tenant's requests so the limits below cannot be raced.
    TenantProfile.objects.select_for_update().get(pk=tenant.pk)
    if problem := bookable_problem(unit):
        raise ValidationError(problem)
    if ViewingRequest.objects.filter(tenant=tenant, unit=unit, status__in=ViewingRequest.ACTIVE_STATUSES).exists():
        raise Conflict("You already have an open viewing request for this home.", code="duplicate_request")
    if ViewingRequest.objects.filter(tenant=tenant, status__in=ViewingRequest.ACTIVE_STATUSES).count() >= MAX_ACTIVE_REQUESTS:
        raise ValidationError(f"You can have up to {MAX_ACTIVE_REQUESTS} open viewing requests. Cancel one or wait for a reply first.")
    try:
        with transaction.atomic():
            item = ViewingRequest.objects.create(tenant=tenant, unit=unit, note=note[:500], preferred_times=preferred_times or [])
    except IntegrityError:
        raise Conflict("You already have an open viewing request for this home.", code="duplicate_request")
    reserve_viewing_credit(item)
    audit(user, "viewing_request.created", item, unit_id=unit.pk)
    notify(recipient=unit.property.landlord.user, event="viewing.requested", dedupe_key=f"viewing-request:{item.pk}:landlord",
           title="New viewing request",
           message=f"A tenant asked to view {unit.title}. Approve with a time, or decline, from your dashboard.",
           link="/landlord?tab=viewings")
    return item


def _lock(request_id):
    return (ViewingRequest.objects.select_for_update(of=("self",))
            .select_related("unit__property__landlord__user", "tenant__user").get(pk=request_id))


@transaction.atomic
def cancel_request(request_id, user, *, reason=""):
    item = _lock(request_id)
    party = party_for(user, item)
    if party is None:
        raise PermissionDenied("You are not part of this viewing request.")
    if item.status not in ViewingRequest.ACTIVE_STATUSES:
        raise ValidationError("This request is no longer open.")
    viewing = getattr(item, "viewing", None)
    if viewing and viewing.status != Viewing.Status.SCHEDULED:
        raise ValidationError("This viewing has already taken place; report the outcome instead.")
    previous = item.status
    item.status = ViewingRequest.Status.CANCELLED
    item.cancelled_by = party
    item.cancel_reason = reason[:300]
    item.save(update_fields=["status", "cancelled_by", "cancel_reason", "updated_at"])
    if viewing:
        viewing.status = Viewing.Status.CANCELLED
        viewing.save(update_fields=["status", "updated_at"])
    # The tenant gets the credit back unless they cancel an already-approved viewing themselves.
    credit_returned = previous == ViewingRequest.Status.PENDING or party != ViewingRequest.Party.TENANT
    settle_viewing_credit(item, restore=credit_returned, include_consumed=party != ViewingRequest.Party.TENANT)
    audit(user, "viewing_request.cancelled", item, **{"from": previous, "to": item.status, "by": party, "credit_returned": credit_returned})
    if party == ViewingRequest.Party.TENANT:
        if previous == ViewingRequest.Status.APPROVED:
            notify(recipient=item.unit.property.landlord.user, event="viewing.cancelled", dedupe_key=f"viewing-request:{item.pk}:cancelled:landlord",
                   title="Viewing cancelled", message=f"The tenant cancelled the viewing for {item.unit.title}.", link="/landlord?tab=viewings")
    else:
        notify(recipient=item.tenant.user, event="viewing.cancelled", dedupe_key=f"viewing-request:{item.pk}:cancelled:tenant",
               title="Viewing cancelled",
               message=f"The viewing for {item.unit.title} was cancelled by the {'landlord' if party == 'landlord' else 'Nyumbani team'}. "
                       "Your viewing credit has been returned.", link="/tenant")
    return item


@transaction.atomic
def reject_request(request_id, user, *, note=""):
    item = _lock(request_id)
    if not is_landlord_for(user, item) and not is_platform_admin(user):
        raise PermissionDenied("Only the listing landlord can act on this request.")
    if item.status != ViewingRequest.Status.PENDING:
        raise ValidationError("Only pending requests can be declined.")
    item.status = ViewingRequest.Status.REJECTED
    item.landlord_note = note[:500]
    item.responded_at = timezone.now()
    item.save(update_fields=["status", "landlord_note", "responded_at", "updated_at"])
    settle_viewing_credit(item, restore=True)
    audit(user, "viewing_request.rejected", item, **{"from": "pending_landlord", "to": "rejected", "has_note": bool(item.landlord_note)})
    notify(recipient=item.tenant.user, event="viewing.rejected", dedupe_key=f"viewing-request:{item.pk}:rejected:tenant",
           title="Viewing request declined",
           message=f"Your viewing request for {item.unit.title} was declined and your credit was returned. Browse other homes in the area.",
           link="/tenant")
    return item


def _validate_time(scheduled_at):
    now = timezone.now()
    if scheduled_at <= now:
        raise ValidationError({"scheduled_at": "Choose a future viewing time."})
    if scheduled_at > now + timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationError({"scheduled_at": f"Choose a time within the next {MAX_DAYS_AHEAD} days."})


@transaction.atomic
def approve_request(request_id, user, *, scheduled_at, meeting_note=""):
    item = _lock(request_id)
    if not is_landlord_for(user, item) and not is_platform_admin(user):
        raise PermissionDenied("Only the listing landlord can act on this request.")
    if item.status != ViewingRequest.Status.PENDING:
        raise ValidationError("Only pending requests can be approved.")
    if problem := bookable_problem(item.unit):
        raise ValidationError(problem)
    _validate_time(scheduled_at)
    item.status = ViewingRequest.Status.APPROVED
    item.responded_at = timezone.now()
    item.save(update_fields=["status", "responded_at", "updated_at"])
    settle_viewing_credit(item)
    viewing = Viewing.objects.create(request=item, scheduled_at=scheduled_at, meeting_note=meeting_note[:500])
    audit(user, "viewing.scheduled", viewing, request_id=item.pk, scheduled_at=scheduled_at.isoformat(), **{"from": "pending_landlord", "to": "approved"})
    notify(recipient=item.tenant.user, event="viewing.approved", dedupe_key=f"viewing:{viewing.pk}:approved:tenant",
           title="Viewing approved",
           message=f"Your viewing for {item.unit.title} is confirmed for {_when(scheduled_at)}. The address and landlord contact are on your dashboard.",
           link="/tenant")
    return viewing


def _lock_viewing(viewing_id):
    return (Viewing.objects.select_for_update(of=("self",))
            .select_related("request__unit__property__landlord__user", "request__tenant__user").get(pk=viewing_id))


@transaction.atomic
def reschedule_viewing(viewing_id, user, *, scheduled_at, meeting_note=None):
    viewing = _lock_viewing(viewing_id)
    if not is_landlord_for(user, viewing.request) and not is_platform_admin(user):
        raise PermissionDenied("Only the landlord can move a viewing. Tenants can cancel and request again.")
    if viewing.status != Viewing.Status.SCHEDULED:
        raise ValidationError("Only upcoming viewings can be rescheduled.")
    if viewing.reschedule_count >= MAX_RESCHEDULES:
        raise ValidationError("This viewing has been moved too many times. Cancel it instead; the tenant's credit will be returned.")
    _validate_time(scheduled_at)
    previous = viewing.scheduled_at
    viewing.scheduled_at = scheduled_at
    viewing.reschedule_count += 1
    fields = ["scheduled_at", "reschedule_count", "updated_at"]
    if meeting_note is not None:
        viewing.meeting_note = meeting_note[:500]
        fields.append("meeting_note")
    viewing.save(update_fields=fields)
    audit(user, "viewing.rescheduled", viewing, previous=previous.isoformat(), scheduled_at=scheduled_at.isoformat())
    notify(recipient=viewing.request.tenant.user, event="viewing.rescheduled",
           dedupe_key=f"viewing:{viewing.pk}:rescheduled:{viewing.reschedule_count}:tenant", title="Viewing time changed",
           message=f"The landlord moved your viewing for {viewing.request.unit.title} to {_when(scheduled_at)}. "
                   "If the new time does not suit you, you can cancel from your dashboard.", link="/tenant")
    return viewing


@transaction.atomic
def complete_viewing(viewing_id, user):
    viewing = _lock_viewing(viewing_id)
    party = party_for(user, viewing.request)
    if party not in (ViewingRequest.Party.TENANT, ViewingRequest.Party.LANDLORD):
        raise PermissionDenied("You are not involved in this viewing.")
    if viewing.status != Viewing.Status.SCHEDULED:
        raise ValidationError("Only scheduled viewings may be completed.")
    if viewing.scheduled_at > timezone.now() + timedelta(hours=1):
        raise ValidationError("This viewing has not happened yet.")
    viewing.status = Viewing.Status.OUTCOME_PENDING
    viewing.completed_at = timezone.now()
    viewing.save(update_fields=["status", "completed_at", "updated_at"])
    audit(user, "viewing.completed", viewing, **{"from": "scheduled", "to": "outcome_pending", "actor_role": party})
    return viewing


def _open_dispute(viewing, user, reason):
    dispute, created = Dispute.objects.get_or_create(viewing=viewing, defaults={"opened_by": user, "reason": reason})
    if created:
        audit(user, "viewing.dispute_opened", dispute, viewing_id=viewing.pk)
    raise_flag(viewing, ReferralFlag.Reason.OUTCOME_CONFLICT, detail=reason)
    return dispute


@transaction.atomic
def report_outcome(viewing_id, user, *, choice, note=""):
    """Record one party's account of what happened. Returns (outcome, created, fee_or_None)."""
    viewing = _lock_viewing(viewing_id)
    party = party_for(user, viewing.request)
    if party not in (ViewingRequest.Party.TENANT, ViewingRequest.Party.LANDLORD):
        raise PermissionDenied("Only the viewing tenant and landlord may report an outcome.")
    if viewing.status == Viewing.Status.SCHEDULED and viewing.scheduled_at <= timezone.now():
        viewing.status = Viewing.Status.OUTCOME_PENDING
        viewing.completed_at = timezone.now()
        viewing.save(update_fields=["status", "completed_at", "updated_at"])
    within_window = viewing.scheduled_at >= timezone.now() - timedelta(days=settings.REFERRAL_ATTRIBUTION_DAYS)
    late_rental = viewing.status == Viewing.Status.DID_NOT_RENT and choice == Outcome.Choice.RENTED and within_window
    if viewing.status not in OUTCOME_DUE_STATUSES and not late_rental:
        raise ValidationError("An outcome is not due for this viewing.")
    outcome, created = Outcome.objects.update_or_create(viewing=viewing, reporter=user, defaults={"choice": choice, "note": note[:500]})
    reports = {o.reporter_id: o.choice for o in viewing.outcomes.all()}
    tenant_choice = reports.get(viewing.request.tenant.user_id)
    landlord_choice = reports.get(viewing.request.unit.property.landlord.user_id)
    audit(user, "viewing.outcome_reported", outcome, choice=choice, actor_role=party, viewing_id=viewing.pk)

    fee = None
    if landlord_choice == Outcome.Choice.RENTED:
        fee, _ = finalize_rental(viewing, actor=user, source=ReferralFee.Source.LANDLORD_REPORT)
    elif Outcome.Choice.DISPUTED in (tenant_choice, landlord_choice):
        viewing.status = Viewing.Status.DISPUTED
        _open_dispute(viewing, user, "A party disputed the viewing outcome.")
    elif tenant_choice == Outcome.Choice.RENTED:
        if landlord_choice is not None:
            viewing.status = Viewing.Status.DISPUTED
            _open_dispute(viewing, user, "The tenant reported renting the home; the landlord did not.")
        else:
            viewing.status = Viewing.Status.OUTCOME_PENDING
            flag = raise_flag(viewing, ReferralFlag.Reason.TENANT_REPORTED_RENTED, detail="Tenant reported renting this home.")
            if flag:
                notify(recipient=viewing.request.unit.property.landlord.user, event="referral.confirm_requested",
                       dedupe_key=f"referral-flag:{flag.pk}:landlord", title="Please confirm the viewing outcome",
                       message=f"The tenant who viewed {viewing.request.unit.title} reported renting it. Please confirm on your dashboard.",
                       link="/landlord?tab=viewings")
    elif tenant_choice and landlord_choice:
        if tenant_choice == landlord_choice:
            viewing.status = tenant_choice
        else:
            viewing.status = Viewing.Status.DISPUTED
            _open_dispute(viewing, user, "The tenant and landlord reported different outcomes.")
    else:
        viewing.status = Viewing.Status.STILL_DECIDING if choice == Outcome.Choice.STILL_DECIDING else Viewing.Status.OUTCOME_PENDING
    if not fee:
        viewing.save(update_fields=["status", "updated_at"])
    return outcome, created, fee


def expire_stale_requests(now=None):
    """Expire requests the landlord never answered and return the tenant's credit."""
    now = now or timezone.now()
    expired = 0
    stale_ids = ViewingRequest.objects.filter(status=ViewingRequest.Status.PENDING,
                                              created_at__lt=now - timedelta(days=PENDING_EXPIRY_DAYS)).values_list("pk", flat=True)
    for request_id in list(stale_ids):
        with transaction.atomic():
            item = _lock(request_id)
            if item.status != ViewingRequest.Status.PENDING:
                continue
            item.status = ViewingRequest.Status.EXPIRED
            item.cancelled_by = ViewingRequest.Party.SYSTEM
            item.save(update_fields=("status", "cancelled_by", "updated_at"))
            settle_viewing_credit(item, restore=True)
            audit(None, "viewing_request.expired", item)
            notify(recipient=item.tenant.user, event="viewing.expired", dedupe_key=f"viewing-request:{item.pk}:expired:tenant",
                   title="Viewing request expired",
                   message=f"Your viewing request for {item.unit.title} expired without a reply. Your credit was returned.", link="/tenant")
            notify(recipient=item.unit.property.landlord.user, event="viewing.expired", dedupe_key=f"viewing-request:{item.pk}:expired:landlord",
                   title="Viewing request expired",
                   message=f"A viewing request for {item.unit.title} expired after {PENDING_EXPIRY_DAYS} days without a response.",
                   link="/landlord?tab=viewings")
            expired += 1
    return expired


TIMELINE_LABELS = {
    "viewing_request.created": "Viewing requested",
    "viewing_request.rejected": "Request declined",
    "viewing_request.cancelled": "Cancelled",
    "viewing_request.expired": "Request expired without a reply",
    "viewing.scheduled": "Viewing approved and scheduled",
    "viewing.rescheduled": "Viewing time changed",
    "viewing.completed": "Viewing marked as done",
    "viewing.outcome_reported": "Outcome reported",
    "viewing.dispute_opened": "Outcomes differ — sent for review",
    "referral.ruling": "Outcome reviewed by Nyumbani",
    "referral.fee_created": "Rental recorded",
}


def timeline(item):
    """Booking history for the parties, from the tamper-evident audit log. Shows roles, never identities."""
    viewing = getattr(item, "viewing", None)
    query = Q(object_type="viewings.ViewingRequest", object_id=str(item.pk))
    if viewing:
        outcome_ids = [str(pk) for pk in viewing.outcomes.values_list("pk", flat=True)]
        query |= Q(object_type="viewings.Viewing", object_id=str(viewing.pk))
        query |= Q(object_type="viewings.Outcome", object_id__in=outcome_ids)
        query |= Q(action="viewing.dispute_opened", metadata__viewing_id=viewing.pk)
        query |= Q(action="referral.fee_created", metadata__viewing_id=viewing.pk)
    tenant_id, landlord_id = item.tenant.user_id, item.unit.property.landlord.user_id
    events = []
    for entry in AuditLog.objects.filter(query).order_by("created_at", "id"):
        if entry.action not in TIMELINE_LABELS:
            continue
        actor = ("tenant" if entry.actor_ref == str(tenant_id) else "landlord" if entry.actor_ref == str(landlord_id)
                 else "system" if not entry.actor_ref else "nyumbani")
        detail = ""
        if entry.action == "viewing.outcome_reported":
            detail = str(entry.metadata.get("choice", "")).replace("_", " ")
        events.append({"action": entry.action, "label": TIMELINE_LABELS[entry.action], "by": actor,
                       "detail": detail, "at": entry.created_at})
    return events
