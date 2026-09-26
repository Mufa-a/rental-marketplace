from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import User

# Accepts 07XXXXXXXX, 01XXXXXXXX, or +2547XXXXXXXX / +2541XXXXXXXX.
phone_validator = RegexValidator(
    regex=r"^(\+?254|0)[17]\d{8}$",
    message="Enter a valid Kenyan phone number, e.g. 0712345678 or +254712345678.",
)


def normalize_phone(raw: str) -> str:
    """Always store/lookup phone numbers in +254XXXXXXXXX form."""
    raw = raw.strip().replace(" ", "")
    if raw.startswith("0"):
        return "+254" + raw[1:]
    if raw.startswith("254"):
        return "+" + raw
    return raw


class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(validators=[phone_validator])
    # Public registration can only create ordinary marketplace accounts.
    # Admin access is provisioned through Django admin, never through OTP signup.
    role = serializers.ChoiceField(
        choices=((User.Role.TENANT, "Tenant"), (User.Role.LANDLORD, "Landlord")),
        required=False,
    )

    def validate_phone_number(self, value):
        return normalize_phone(value)


class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(validators=[phone_validator])
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Code must be 6 digits."})

    def validate_phone_number(self, value):
        return normalize_phone(value)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone_number", "role", "phone_verified", "first_name", "last_name", "email")
        read_only_fields = ("id", "phone_number", "role", "phone_verified")

    def validate_email(self, value):
        return value.strip().lower()
