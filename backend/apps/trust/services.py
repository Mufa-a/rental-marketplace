"""Report moderation: auto-hide on repeated reports, resolving reports, suspending landlords.

Suspension reuses the existing convention that a *verified but inactive* account was
deactivated by an administrator (see accounts.services.verify_otp), so a suspended
landlord cannot log back in by passing an OTP.
"""
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.properties.models import Unit

from .models import AccountRestriction, Report

# Reasons that count toward auto-hide. Harassment / "other" still reach the admin queue
# but should not, on their own, take a listing offline.
SERIOUS_REASONS = ("fraudulent_listing", "suspicious_payment_request", "misleading_information")


def auto_hide_threshold() -> int:
    return getattr(settings, "REPORT_AUTO_HIDE_THRESHOLD", 3)


def _bust_public_cache():
    cache.add("public-listings:version", 1, timeout=None)
    cache.incr("public-listings:version")


def _audit(actor, action, obj, **metadata):
    AuditLog.objects.create(actor=actor, action=action, object_type=obj._meta.label, object_id=str(obj.pk), metadata=metadata)


def maybe_auto_hide(unit: Unit) -> bool:
    """Take the unit offline once enough different people have reported it. Returns True if hidden."""
    if not unit.is_published:
        return False
    open_serious = Report.objects.filter(listing=unit, resolved_at__isnull=True, reason__in=SERIOUS_REASONS).count()
    if open_serious < auto_hide_threshold():
        return False
    unit.is_published = False
    unit.moderation_hold = True
    unit.save(update_fields=["is_published", "moderation_hold", "updated_at"])
    _audit(None, "unit.auto_hidden", unit, open_reports=open_serious)
    _bust_public_cache()
    return True


@transaction.atomic
def resolve_reports(reports, resolution: str, admin: User) -> int:
    """Close open reports. Does not change listing visibility; that is a separate decision."""
    now = timezone.now()
    count = 0
    for report in reports.filter(resolved_at__isnull=True):
        report.resolved_at, report.resolution, report.resolved_by = now, resolution, admin
        report.save(update_fields=["resolved_at", "resolution", "resolved_by"])
        _audit(admin, "report.resolved", report, resolution=resolution)
        count += 1
    return count


@transaction.atomic
def hide_reported_listings(reports, admin: User) -> int:
    """Unpublish and hold every listing referenced by the given reports."""
    units = Unit.objects.filter(pk__in=reports.exclude(listing=None).values("listing_id"))
    hidden = 0
    for unit in units:
        unit.is_published, unit.moderation_hold = False, True
        unit.save(update_fields=["is_published", "moderation_hold", "updated_at"])
        _audit(admin, "unit.hidden_by_admin", unit)
        hidden += 1
    if hidden:
        _bust_public_cache()
    return hidden


@transaction.atomic
def suspend_landlord(user: User, reason: str, admin: User) -> None:
    """Deactivate the account, record why, and take every one of their listings offline."""
    AccountRestriction.objects.create(user=user, reason=reason[:255])
    user.is_active = False
    user.save(update_fields=["is_active"])
    Unit.objects.filter(property__landlord__user=user).update(is_published=False, moderation_hold=True, updated_at=timezone.now())
    _audit(admin, "user.suspended", user, reason=reason)
    _bust_public_cache()


@transaction.atomic
def lift_suspension(user: User, admin: User) -> None:
    """Reactivate the account and clear holds. Listings stay unpublished until the landlord republishes."""
    now = timezone.now()
    AccountRestriction.objects.filter(user=user).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).update(expires_at=now)
    user.is_active = True
    user.save(update_fields=["is_active"])
    Unit.objects.filter(property__landlord__user=user).update(moderation_hold=False)
    _audit(admin, "user.suspension_lifted", user)
