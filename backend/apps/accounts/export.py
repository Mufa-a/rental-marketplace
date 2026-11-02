"""Self-service copy of a user's personal data (Kenya Data Protection Act, 2019, s.26 right of access).

Includes what the platform holds *about the requesting user*. Other people's identities are left out:
counterparties appear only as their role, and reports about the user omit who filed them.
Verification documents themselves are not re-sent (only what was submitted and the decision).
"""
from django.utils import timezone

from apps.core.models import AuditLog


def _dt(value):
    return value.isoformat() if value else None


def build_export(user):
    from apps.notifications.models import Notification
    from apps.payments.models import Payment
    from apps.properties.models import Property, SavedUnit
    from apps.referrals.models import ReferralFee
    from apps.trust.models import Report
    from apps.verification.models import LandlordVerification
    from apps.viewings.models import Outcome, ViewingRequest

    data = {
        "generated_at": _dt(timezone.now()),
        "about": "A copy of the personal data Nyumbani holds about you. Other people's details are not included.",
        "account": {
            "phone_number": user.phone_number, "role": user.role, "first_name": user.first_name, "last_name": user.last_name,
            "email": user.email, "phone_verified": user.phone_verified, "created_at": _dt(user.created_at),
            "last_login": _dt(user.last_login),
        },
        "consents": [{"type": c.consent_type, "granted": c.granted, "policy_version": c.policy_version, "at": _dt(c.created_at)}
                     for c in user.consents.order_by("created_at")],
        "deletion_requests": [{"status": d.status, "reason": d.reason, "requested_at": _dt(d.requested_at), "resolved_at": _dt(d.resolved_at)}
                              for d in user.deletion_requests.all()],
    }
    requests = ViewingRequest.objects.filter(tenant__user=user).select_related("unit__property", "viewing")
    data["viewing_requests_made"] = [{
        "home": r.unit.title, "area": r.unit.property.area, "town": r.unit.property.city, "status": r.status,
        "your_message": r.note, "preferred_times": r.preferred_times, "landlord_reply": r.landlord_note,
        "requested_at": _dt(r.created_at), "responded_at": _dt(r.responded_at),
        "viewing_time": _dt(getattr(getattr(r, "viewing", None), "scheduled_at", None)),
        "viewing_status": getattr(getattr(r, "viewing", None), "status", None),
    } for r in requests]
    data["outcomes_you_reported"] = [{"choice": o.choice, "note": o.note, "at": _dt(o.created_at)}
                                     for o in Outcome.objects.filter(reporter=user)]
    data["saved_homes"] = [{"home": s.unit.title, "area": s.unit.property.area, "saved_at": _dt(s.created_at)}
                           for s in SavedUnit.objects.filter(tenant__user=user).select_related("unit__property")]
    payments = Payment.objects.filter(tenant_user=user) | Payment.objects.filter(fee__attribution__landlord__user=user) \
        | Payment.objects.filter(property__landlord__user=user)
    data["payments"] = [{"purpose": p.purpose, "amount": p.amount, "currency": p.currency, "status": p.status,
                         "paying_phone": p.phone_number, "mpesa_receipt": p.provider_receipt, "at": _dt(p.created_at)}
                        for p in payments.distinct().order_by("created_at")]
    data["properties"] = [{
        "name": p.name, "address": p.address_line, "area": p.area, "town": p.city, "county": p.county,
        "verification_status": p.verification_status, "created_at": _dt(p.created_at),
        "units": [{"unit": u.unit_number, "title": u.title, "rent": u.monthly_rent, "available": u.available,
                   "published": u.is_published, "created_at": _dt(u.created_at)} for u in p.units.all()],
    } for p in Property.objects.filter(landlord__user=user).prefetch_related("units")]
    data["viewing_requests_received"] = ViewingRequest.objects.filter(unit__property__landlord__user=user).count()
    data["success_fees"] = [{"amount": f.amount, "status": f.status, "due_at": _dt(f.due_at), "paid_at": _dt(f.paid_at)}
                            for f in ReferralFee.objects.filter(attribution__landlord__user=user)]
    data["landlord_verification"] = [{
        "status": v.status, "legal_name": v.legal_name, "id_type": v.id_type, "id_last4": v.id_last4,
        "relationship": v.relationship, "submitted_at": _dt(v.submitted_at), "reviewed_at": _dt(v.reviewed_at),
        "reviewer_note": v.reviewer_note, "documents": [d.get_kind_display() for d in v.documents.all()],
        "documents_deleted_at": _dt(v.documents_purged_at),
    } for v in LandlordVerification.objects.filter(landlord__user=user).prefetch_related("documents")]
    data["reports_you_filed"] = [{"reason": r.reason, "detail": r.detail, "listing": r.listing.title if r.listing_id else None,
                                  "at": _dt(r.created_at), "resolution": r.resolution}
                                 for r in Report.objects.filter(reporter=user).select_related("listing")]
    data["reports_about_you"] = [{"reason": r.reason, "at": _dt(r.created_at), "resolution": r.resolution}
                                 for r in Report.objects.filter(reported_user=user)]
    data["notifications"] = [{"title": n.title, "message": n.message, "channel": n.channel, "at": _dt(n.created_at)}
                             for n in Notification.objects.filter(recipient=user).order_by("created_at")]
    data["activity_log"] = [{"action": e.action, "at": _dt(e.created_at)}
                            for e in AuditLog.objects.filter(actor_ref=str(user.pk)).order_by("id")[:5000]]
    return data
