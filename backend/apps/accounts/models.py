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
