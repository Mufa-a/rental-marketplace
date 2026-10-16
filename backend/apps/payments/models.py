from django.db import models

class Payment(models.Model):
    class Purpose(models.TextChoices):
        REFERRAL_FEE = "referral_fee", "Landlord referral fee"
        VIEWING_CREDITS = "viewing_credits", "Tenant viewing credits"
        VERIFICATION_FEE = "verification_fee", "Property verification fee"
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        DISPUTED = "disputed", "Disputed"
    fee = models.ForeignKey("referrals.ReferralFee", on_delete=models.PROTECT, related_name="payments", null=True, blank=True)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.REFERRAL_FEE)
    tenant_user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="viewing_credit_payments", null=True, blank=True)
    property = models.ForeignKey("properties.Property", on_delete=models.PROTECT, related_name="verification_payments", null=True, blank=True)
    credits = models.PositiveSmallIntegerField(null=True, blank=True)
    amount = models.PositiveIntegerField()
    phone_number = models.CharField(max_length=20)
    provider_reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    idempotency_key = models.CharField(max_length=100, unique=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ViewingCreditPurchase(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="credit_purchase")
    tenant = models.ForeignKey("accounts.TenantProfile", on_delete=models.PROTECT, related_name="credit_purchases")
    credits_total = models.PositiveSmallIntegerField()
    credits_remaining = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class ViewingCreditUse(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        CONSUMED = "consumed", "Consumed"
        RESTORED = "restored", "Restored"

    purchase = models.ForeignKey(ViewingCreditPurchase, on_delete=models.PROTECT, related_name="uses")
    viewing_request = models.OneToOneField("viewings.ViewingRequest", on_delete=models.PROTECT, related_name="credit_use")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RESERVED)
    created_at = models.DateTimeField(auto_now_add=True)
