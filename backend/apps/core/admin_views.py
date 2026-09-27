from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.payments.models import Payment
from apps.properties.models import Property, Unit
from apps.referrals.models import ReferralFee
from apps.trust.models import Report
from apps.viewings.models import Outcome, Viewing, ViewingRequest

# Human-readable labels for AuditLog.action values written across the codebase
# (apps/properties/views.py and apps/viewings/views.py). Kept here rather than
# on AuditLog itself since the feed is an admin-only presentation concern.
ACTIVITY_LABELS = {
    "property.created": "Property listed",
    "property.updated": "Property updated",
    "property.deleted": "Property removed",
    "unit.created": "Unit added",
    "unit.updated": "Unit updated",
    "unit.deleted": "Unit removed",
    "unit.availability_confirmed": "Availability confirmed",
    "unit.saved": "Unit saved by tenant",
    "unit.unsaved": "Unit unsaved by tenant",
    "property_media.created": "Photo added",
    "property_media.deleted": "Photo removed",
    "viewing_request.created": "Viewing requested",
    "viewing_request.cancelled": "Viewing request cancelled",
    "viewing_request.rejected": "Viewing request declined",
    "viewing.scheduled": "Viewing scheduled",
    "viewing.completed": "Viewing completed",
    "viewing.outcome_reported": "Viewing outcome reported",
    "viewing.dispute_opened": "Viewing outcome disputed",
}


def _focus_items():
    """Operational queue items an admin should look at today.

    Every count and timestamp here comes straight from the database — nothing
    is invented. Severity is derived from simple, explainable business rules
    (age of the oldest item), not arbitrary flags.
    """
    now = timezone.now()
    items = []

    pending_properties = Property.objects.filter(
        verification_status=Property.VerificationStatus.PENDING
    ).order_by("created_at")
    pending_count = pending_properties.count()
    if pending_count:
        oldest = pending_properties.first()
        age_days = (now - oldest.created_at).days
        items.append({
            "key": "pending_approvals",
            "label": "Properties awaiting approval",
            "count": pending_count,
            "detail": f"Oldest submitted {age_days} day{'s' if age_days != 1 else ''} ago"
                      f" ({oldest.name}).",
            "severity": "high" if age_days >= 3 else "medium",
            "action_label": "Review properties",
        })

    open_reports = Report.objects.filter(resolved_at__isnull=True).order_by("created_at")
    open_reports_count = open_reports.count()
    if open_reports_count:
        oldest = open_reports.first()
        age_days = (now - oldest.created_at).days
        items.append({
            "key": "open_reports",
            "label": "Open reports & complaints",
            "count": open_reports_count,
            "detail": f"Oldest report: \u201c{oldest.reason}\u201d, {age_days} day"
                      f"{'s' if age_days != 1 else ''} old.",
            "severity": "high",
            "action_label": "Review reports",
        })

    pending_requests = ViewingRequest.objects.filter(status=ViewingRequest.Status.PENDING)
    pending_requests_count = pending_requests.count()
    if pending_requests_count:
        oldest = pending_requests.order_by("created_at").first()
        age_hours = int((now - oldest.created_at).total_seconds() // 3600)
        items.append({
            "key": "pending_viewing_requests",
            "label": "Viewing requests awaiting a landlord reply",
            "count": pending_requests_count,
            "detail": f"Oldest has waited {age_hours} hour{'s' if age_hours != 1 else ''}.",
            "severity": "medium" if age_hours >= 48 else "low",
            "action_label": "View requests",
        })

    awaiting_outcome = Viewing.objects.filter(
        Q(status=Viewing.Status.OUTCOME_PENDING)
        | Q(status=Viewing.Status.SCHEDULED, scheduled_at__lte=now)
    ).count()
    if awaiting_outcome:
        items.append({
            "key": "awaiting_outcome",
            "label": "Completed viewings missing an outcome",
            "count": awaiting_outcome,
            "detail": "Tenant or landlord has not yet reported what happened.",
            "severity": "medium",
            "action_label": "View viewings",
        })

    unpublished_units = Unit.objects.filter(is_published=False).count()
    if unpublished_units:
        items.append({
            "key": "unpublished_units",
            "label": "Units not yet published",
            "count": unpublished_units,
            "detail": "Listed by a landlord but not visible in search.",
            "severity": "low",
            "action_label": "View units",
        })

    disputed = Viewing.objects.filter(status=Viewing.Status.DISPUTED).count()
    if disputed:
        items.append({
            "key": "disputed_viewings",
            "label": "Disputed viewing outcomes",
            "count": disputed,
            "detail": "Tenant and landlord reported conflicting outcomes.",
            "severity": "high",
            "action_label": "View disputes",
        })

    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda item: order[item["severity"]])
    return items


def _area_insights():
    """Per-area supply/demand snapshot, built only from data that exists today."""
    supply = (
        Unit.objects.filter(property__is_active=True)
        .values("property__city", "property__area")
        .annotate(
            active_listings=Count("id", filter=Q(available=True, is_published=True)),
            total_units=Count("id"),
            avg_rent=Avg("monthly_rent", filter=Q(is_published=True)),
        )
    )
    demand_rows = (
        ViewingRequest.objects.values("unit__property__city", "unit__property__area")
        .annotate(count=Count("id"))
    )
    demand = {(row["unit__property__city"], row["unit__property__area"]): row["count"] for row in demand_rows}

    areas = []
    for row in supply:
        key = (row["property__city"], row["property__area"])
        viewing_requests = demand.get(key, 0)
        active = row["active_listings"] or 0
        areas.append({
            "city": row["property__city"],
            "area": row["property__area"],
            "active_listings": active,
            "total_units": row["total_units"],
            "avg_rent_ksh": round(row["avg_rent"]) if row["avg_rent"] else None,
            "viewing_requests": viewing_requests,
            "demand_per_listing": round(viewing_requests / active, 2) if active else None,
        })
    areas.sort(key=lambda item: item["viewing_requests"], reverse=True)
    return areas[:15]


def _recent_activity():
    entries = AuditLog.objects.select_related("actor").order_by("-created_at")[:20]
    return [{
        "action": entry.action,
        "label": ACTIVITY_LABELS.get(entry.action, entry.action.replace("_", " ").replace(".", " · ")),
        "object_type": entry.object_type.split(".")[-1],
        "object_id": entry.object_id,
        "actor": entry.actor.phone_number if entry.actor else "System",
        "created_at": entry.created_at,
    } for entry in entries]


class AdminOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.ADMIN or not request.user.is_staff:
            return Response({"error": {"code": "admin_only", "message": "Admin access is required."}}, status=403)

        latest_requests = ViewingRequest.objects.select_related(
            "tenant__user", "unit__property__landlord__user", "unit"
        ).order_by("-created_at")[:12]
        latest_fees = ReferralFee.objects.select_related(
            "attribution__landlord__user", "attribution__viewing__request__unit"
        ).order_by("-created_at")[:12]
        latest_payments = Payment.objects.select_related(
            "fee__attribution__landlord__user", "tenant_user"
        ).order_by("-created_at")[:12]
        latest_viewings = Viewing.objects.select_related(
            "request__unit__property", "request__tenant__user"
        ).prefetch_related("outcomes").order_by("-created_at")[:12]

        return Response({
            "metrics": {
                "tenants": User.objects.filter(role=User.Role.TENANT).count(),
                "landlords": User.objects.filter(role=User.Role.LANDLORD).count(),
                "properties": Property.objects.count(),
                "units": Unit.objects.count(),
                "active_listings": Unit.objects.filter(available=True, is_published=True, property__is_active=True).count(),
                "pending_approvals": Property.objects.filter(verification_status=Property.VerificationStatus.PENDING).count(),
                "viewing_requests": ViewingRequest.objects.count(),
                "pending_viewings": Viewing.objects.filter(
                    Q(status=Viewing.Status.OUTCOME_PENDING)
                    | Q(status=Viewing.Status.SCHEDULED, scheduled_at__lte=timezone.now())
                ).count(),
                "rentals_reported": Viewing.objects.filter(status=Viewing.Status.RENTED).count(),
                "open_reports": Report.objects.filter(resolved_at__isnull=True).count(),
                "fees_due": ReferralFee.objects.filter(status=ReferralFee.Status.PENDING).count(),
                "fees_collected_ksh": Payment.objects.filter(
                    purpose=Payment.Purpose.REFERRAL_FEE, status=Payment.Status.SUCCESSFUL
                ).aggregate(total=Sum("amount"))["total"] or 0,
                "bundle_revenue_ksh": Payment.objects.filter(
                    purpose=Payment.Purpose.VIEWING_CREDITS, status=Payment.Status.SUCCESSFUL
                ).aggregate(total=Sum("amount"))["total"] or 0,
                "failed_payments": Payment.objects.filter(status=Payment.Status.FAILED).count(),
            },
            "focus": _focus_items(),
            "areas": _area_insights(),
            "recent_activity": _recent_activity(),
            "viewing_requests": [{
                "id": item.pk, "status": item.status, "unit": item.unit.title,
                "property": item.unit.property.name, "tenant": item.tenant.user.phone_number,
                "landlord": item.unit.property.landlord.user.phone_number,
                "rent": item.unit.monthly_rent, "created_at": item.created_at,
            } for item in latest_requests],
            "viewings": [{
                "id": item.pk, "status": item.status, "unit": item.request.unit.title,
                "property": item.request.unit.property.name,
                "scheduled_at": item.scheduled_at,
                "outcomes": [{"reporter": outcome.reporter.phone_number, "choice": outcome.choice}
                             for outcome in item.outcomes.all()],
            } for item in latest_viewings],
            "fees": [{
                "id": fee.pk, "amount": fee.amount, "status": fee.status,
                "unit": fee.attribution.viewing.request.unit.title,
                "landlord": fee.attribution.landlord.user.phone_number,
                "due_at": fee.due_at, "created_at": fee.created_at,
            } for fee in latest_fees],
            "payments": [{
                "id": payment.pk, "purpose": payment.purpose, "amount": payment.amount,
                "status": payment.status, "phone_number": payment.phone_number,
                "payer": payment.fee.attribution.landlord.user.phone_number if payment.fee_id else payment.tenant_user.phone_number,
                "created_at": payment.created_at,
            } for payment in latest_payments],
        })
