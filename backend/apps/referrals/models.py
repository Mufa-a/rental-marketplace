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
    attribution = models.OneToOneField(ReferralAttribution, on_delete=models.PROTECT, related_name="fee")
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
