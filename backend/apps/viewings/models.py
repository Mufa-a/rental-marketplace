"""Viewing requests, scheduled viewings, and independently submitted outcomes."""
from django.db import models


class ViewingRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending_landlord", "Pending landlord"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    tenant = models.ForeignKey("accounts.TenantProfile", on_delete=models.CASCADE, related_name="viewing_requests")
    unit = models.ForeignKey("properties.Unit", on_delete=models.PROTECT, related_name="viewing_requests")
    preferred_times = models.JSONField(default=list, blank=True)
    note = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    landlord_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "status"], name="viewings_vi_tenant__d5ce61_idx"),
            models.Index(fields=["unit", "status"], name="viewings_vi_unit_id_08380c_idx"),
        ]
        ordering = ("-created_at",)


class Viewing(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        OUTCOME_PENDING = "outcome_pending", "Outcome pending"
        RENTED = "rented", "Rented"
        DID_NOT_RENT = "did_not_rent", "Did not rent"
        STILL_DECIDING = "still_deciding", "Still deciding"
        DISPUTED = "disputed", "Disputed"
        RESCHEDULED = "rescheduled", "Rescheduled"
        NO_SHOW = "no_show", "No show"
        CANCELLED = "cancelled", "Cancelled"

    request = models.OneToOneField(ViewingRequest, on_delete=models.PROTECT, related_name="viewing")
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    meeting_note = models.CharField(max_length=500, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Outcome(models.Model):
    class Choice(models.TextChoices):
        RENTED = "rented", "Rented"
        DID_NOT_RENT = "did_not_rent", "Did not rent"
        STILL_DECIDING = "still_deciding", "Still deciding"
        NO_SHOW = "no_show", "No show"
        DISPUTED = "disputed", "Disputed"

    viewing = models.ForeignKey(Viewing, on_delete=models.CASCADE, related_name="outcomes")
    reporter = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="viewing_outcomes")
    choice = models.CharField(max_length=20, choices=Choice.choices)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["viewing", "reporter"], name="one_outcome_per_reporter")]
