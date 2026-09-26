from django.db import models

class Report(models.Model):
    reporter = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="reports_made")
    reported_user = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="reports_received")
    listing = models.ForeignKey("properties.Unit", null=True, blank=True, on_delete=models.PROTECT)
    reason = models.CharField(max_length=100)
    detail = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
