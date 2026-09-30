"""
Identity & auth — Phase 2.

User is phone-anchored (not email/username first) per the OTP-based auth
design: phone is verified via OTP before an account is usable. Role is a
flat field rather than separate Tenant/Landlord tables at the User level,
so switching or adding a role later doesn't require a schema migration —
TenantProfile/LandlordProfile hold the role-specific data instead.
"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class MarketplaceUserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("A phone number is required.")
        extra_fields.setdefault("username", phone_number)
        extra_fields.setdefault("role", "tenant")
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("phone_verified", True)
        extra_fields.setdefault("role", "admin")
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_staff=True and is_superuser=True.")
        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        TENANT = "tenant", "Tenant"
        LANDLORD = "landlord", "Landlord"
        ADMIN = "admin", "Admin"

    phone_number = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []
    objects = MarketplaceUserManager()

    @classmethod
    def normalize_username(cls, username):
        return username

    def __str__(self):
        return f"{self.phone_number} ({self.role})"


class OTPCode(models.Model):
    """Single-use, short-lived phone verification code. Never stored plaintext."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otp_codes")
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "expires_at"])]


class TenantProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="tenant_profile")
    reliability_score = models.DecimalField(max_digits=4, decimal_places=1, default=100.0)
    created_at = models.DateTimeField(auto_now_add=True)


class LandlordProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="landlord_profile")
    reliability_score = models.DecimalField(max_digits=4, decimal_places=1, default=100.0)
    verification_tier = models.CharField(
        max_length=20,
        choices=[("basic", "Basic"), ("standard", "Standard"), ("trusted", "Trusted")],
        default="basic",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class ConsentRecord(models.Model):
    """Append-only history of what a user agreed to, and which policy version they saw.

    A withdrawal is a new row with granted=False; earlier rows are never edited,
    so the latest row per (user, consent_type) is the current state.
    """

    class ConsentType(models.TextChoices):
        TERMS_PRIVACY = "terms_privacy", "Terms & Conditions and Privacy Policy"
        MARKETING = "marketing", "Marketing communications"
        ANALYTICS = "analytics", "Optional analytics"
        LOCATION = "location", "Location-based search"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="consents")
    consent_type = models.CharField(max_length=20, choices=ConsentType.choices)
    granted = models.BooleanField()
    policy_version = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "consent_type", "-created_at"], name="consent_user_type_idx")]
        ordering = ("-created_at", "-id")


class AccountDeletionRequest(models.Model):
    """A user's request to delete their account, processed by a human admin.

    Deletion is not automated: some records (payments, audit logs, viewing
    outcomes tied to fees) may need to be retained, so an administrator
    reviews each request. The row deliberately survives user deletion.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        CANCELLED = "cancelled", "Cancelled by user"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected / retained"

    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="deletion_requests")
    phone_last4 = models.CharField(max_length=4, blank=True)
    role = models.CharField(max_length=10, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    admin_note = models.CharField(max_length=500, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-requested_at",)
        constraints = [
            models.UniqueConstraint(fields=("user",), condition=models.Q(status="pending"), name="one_pending_deletion_request_per_user"),
        ]
