"""Viewing workflow helpers shared by the API and management commands."""
from django.utils import timezone

from apps.core.models import AuditLog
from apps.notifications.services import queue_sms
from apps.payments.services import settle_viewing_credit

from .models import ViewingRequest

UNIT_RENTED_NOTE = "This home has been rented."


def close_requests_for_rented_unit(rented_request):
    """Reject every other pending request for a unit that has just been reported as rented.

    A rented unit can no longer be approved, so these requests would otherwise sit in
    "pending" (holding a reserved credit) until the seven-day expiry. Each tenant gets
    their credit back and a text message. Requests that were already approved are left
    alone: the landlord and tenant have an agreed viewing and that is a human decision.
    Returns the number of requests closed.
    """
    others = (
        ViewingRequest.objects.select_for_update(of=("self",))
        .select_related("tenant__user", "unit")
        .filter(unit_id=rented_request.unit_id, status=ViewingRequest.Status.PENDING)
        .exclude(pk=rented_request.pk)
    )
    closed = 0
    for item in others:
        item.status = ViewingRequest.Status.REJECTED
        item.landlord_note = UNIT_RENTED_NOTE
        item.responded_at = timezone.now()
        item.save(update_fields=("status", "landlord_note", "responded_at", "updated_at"))
        settle_viewing_credit(item, restore=True)
        AuditLog.objects.create(
            actor=None, action="viewing_request.closed_unit_rented", object_type=item._meta.label, object_id=str(item.pk),
            metadata={"from": "pending_landlord", "to": "rejected", "rented_request_id": rented_request.pk},
        )
        queue_sms(
            recipient=item.tenant.user, event="viewing.unit_rented",
            dedupe_key=f"viewing-request:{item.pk}:unit-rented:tenant",
            message=f"{item.unit.title} has been rented, so your viewing request was closed and your viewing credit returned. Browse other available homes.",
        )
        closed += 1
    return closed
