"""Payments, configurable prices, and tenant viewing credits.

Prices are data, not code: administrators manage viewing packages, referral
fee rules and service prices per country, so pricing can differ by market and
change without a deploy. A Payment row copies the amount it was created with,
so later price changes never alter historical transactions.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ViewingPackage(models.Model):
    """A tenant-paid bundle of viewing-request credits, e.g. 5 viewings for KES 150."""

    country = models.CharField(max_length=2, default="KE")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    credits = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    price = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3, default="KES")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("country", "sort_order", "credits")
        constraints = [
            models.UniqueConstraint(fields=("country", "credits"), condition=models.Q(is_active=True), name="one_active_package_per_size"),
        ]

    def __str__(self):
        return f"{self.name} ({self.credits} for {self.currency} {self.price})"


class ReferralFeeRule(models.Model):
    """Success fee a landlord owes when a platform viewing converts to a tenancy.

    Rules are matched on the agreed monthly rent: min_rent <= rent <= max_rent
    (max_rent empty = no upper bound). Either a fixed amount or a percentage of
    one month's rent.
    """

    class FeeType(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENT = "percent", "Percentage of monthly rent"

    country = models.CharField(max_length=2, default="KE")
    min_rent = models.PositiveIntegerField(default=0)
    max_rent = models.PositiveIntegerField(null=True, blank=True)
    fee_type = models.CharField(max_length=8, choices=FeeType.choices, default=FeeType.FIXED)
    amount = models.PositiveIntegerField(default=0, help_text="Fixed fee in the local currency.")
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"),
                                  validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))])
    currency = models.CharField(max_length=3, default="KES")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("country", "min_rent")

    def fee_for(self, rent):
        if self.fee_type == self.FeeType.PERCENT:
            return int((Decimal(rent) * self.percent / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return self.amount

    def __str__(self):
        upper = f"{self.max_rent:,}" if self.max_rent is not None else "∞"
        return f"{self.country} rent {self.min_rent:,}–{upper}"


class ServicePrice(models.Model):
    """Prices for optional, clearly disclosed landlord services."""

    class Code(models.TextChoices):
        PROPERTY_VERIFICATION = "property_verification", "Property verification"

    country = models.CharField(max_length=2, default="KE")
    code = models.CharField(max_length=40, choices=Code.choices)
    amount = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3, default="KES")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("country", "code"), name="one_price_per_service_per_country")]

    def __str__(self):
        return f"{self.get_code_display()} ({self.country}): {self.currency} {self.amount}"


class Payment(models.Model):
    class Purpose(models.TextChoices):
        REFERRAL_FEE = "referral_fee", "Landlord referral fee"
        VIEWING_CREDITS = "viewing_credits", "Tenant viewing credits"
        VERIFICATION_FEE = "verification_fee", "Property verification fee"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled by payer"
        REFUNDED = "refunded", "Refunded"
        DISPUTED = "disputed", "Needs review"

    fee = models.ForeignKey("referrals.ReferralFee", on_delete=models.PROTECT, related_name="payments", null=True, blank=True)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.REFERRAL_FEE)
    tenant_user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="viewing_credit_payments", null=True, blank=True)
    property = models.ForeignKey("properties.Property", on_delete=models.PROTECT, related_name="verification_payments", null=True, blank=True)
    package = models.ForeignKey(ViewingPackage, on_delete=models.PROTECT, related_name="payments", null=True, blank=True)
    credits = models.PositiveSmallIntegerField(null=True, blank=True)
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="KES")
    phone_number = models.CharField(max_length=20)
    provider = models.CharField(max_length=20, default="mpesa")
    provider_reference = models.CharField(max_length=100, unique=True)
    # Safaricom's transaction receipt. Unique, so one M-Pesa payment can never settle two orders.
    provider_receipt = models.CharField(max_length=40, null=True, blank=True, unique=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    failure_reason = models.CharField(max_length=40, blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    callback_received_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    refunded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="refunds_recorded", null=True, blank=True)
    refund_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("status", "created_at"), name="payment_status_created_idx"),
            models.Index(fields=("purpose", "status"), name="payment_purpose_status_idx"),
        ]


class ViewingCreditPurchase(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="credit_purchase")
    tenant = models.ForeignKey("accounts.TenantProfile", on_delete=models.PROTECT, related_name="credit_purchases")
    # Credits can only be spent on listings in the country whose price list they were bought from.
    country = models.CharField(max_length=2, default="KE")
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
    updated_at = models.DateTimeField(auto_now=True)
