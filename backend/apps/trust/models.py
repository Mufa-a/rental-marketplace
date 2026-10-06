from django.db import models

class Report(models.Model):
    class Resolution(models.TextChoices):
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"
        DUPLICATE = "duplicate", "Duplicate"

    reporter = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="reports_made")
    reported_user = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="reports_received")
    listing = models.ForeignKey("properties.Unit", null=True, blank=True, on_delete=models.PROTECT)
    reason = models.CharField(max_length=100)
    detail = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(max_length=10, choices=Resolution.choices, blank=True)
    resolved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports_resolved")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One *open* report per person per listing; they can report again once it is resolved.
            models.UniqueConstraint(fields=("reporter", "listing"), condition=models.Q(resolved_at__isnull=True), name="one_open_report_per_user_per_listing"),
        ]

class Dispute(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"
    viewing = models.ForeignKey("viewings.Viewing", on_delete=models.PROTECT, related_name="disputes")
    opened_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    ruling = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("viewing",), name="one_dispute_per_viewing")]

class AccountRestriction(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="restrictions")
    reason = models.CharField(max_length=255)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
