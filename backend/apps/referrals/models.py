"""Referral attribution: which tenancies started from a platform viewing, and the fees owed.

Anti-bypass design (privacy-respecting): the platform does not track anyone
off-platform. It relies on facts both parties already create on-platform —
an approved, completed viewing; each party's own outcome report; and the
landlord marking the unit occupied — and asks the other party to confirm when
those facts disagree. Conflicts become ReferralFlags for a human to review.
"""
from django.db import models


class ReferralAttribution(models.Model):
    viewing = models.OneToOneField("viewings.Viewing", on_delete=models.PROTECT, related_name="attribution")
    tenant = models.ForeignKey("accounts.TenantProfile", on_delete=models.PROTECT, related_name="attributions")
    landlord = models.ForeignKey("accounts.LandlordProfile", on_delete=models.PROTECT, related_name="attributions")
    expires_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ReferralFee(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        WAIVED = "waived", "Waived"
        DISPUTED = "disputed", "Disputed"

    class Source(models.TextChoices):
        LANDLORD_REPORT = "landlord_report", "Landlord reported the rental"
        ADMIN_RULING = "admin_ruling", "Administrator ruling"

    attribution = models.OneToOneField(ReferralAttribution, on_delete=models.PROTECT, related_name="fee")
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="KES")
    # The rent the fee was calculated from, frozen at conversion time.
    monthly_rent = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.LANDLORD_REPORT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    due_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ReferralFlag(models.Model):
    """A signal that a viewing may have converted to a tenancy without being reported."""

    class Reason(models.TextChoices):
        UNIT_OCCUPIED_AFTER_VIEWING = "occupied_after_viewing", "Unit marked occupied soon after this viewing"
        TENANT_REPORTED_RENTED = "tenant_reported_rented", "Tenant reported renting; landlord has not"
        OUTCOME_CONFLICT = "outcome_conflict", "Tenant and landlord reported different outcomes"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CONFIRMED_RENTED = "confirmed_rented", "Confirmed rented"
        DISMISSED = "dismissed", "Dismissed"

    viewing = models.ForeignKey("viewings.Viewing", on_delete=models.PROTECT, related_name="referral_flags")
    reason = models.CharField(max_length=30, choices=Reason.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    detail = models.CharField(max_length=255, blank=True)
    resolution_note = models.CharField(max_length=500, blank=True)
    resolved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="referral_flags_resolved")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("viewing", "reason"), condition=models.Q(status="open"), name="one_open_flag_per_viewing_reason"),
        ]
