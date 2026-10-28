"""Landlord verification.

A landlord submits who they are and their relationship to the homes they list,
with supporting documents. An administrator reviews the submission. Approval
marks the landlord as verified ("standard" tier); it means the documents were
checked by our team, not that the platform guarantees the landlord or any home.

Data minimisation: only the last four characters of an ID number are stored;
documents live in private storage (never a public URL), are readable only by
administrators through an audited download endpoint, and are deleted
VERIFICATION_DOCUMENT_RETENTION_DAYS after a decision. The decision record stays.
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models


def private_storage():
    if settings.R2_PRIVATE_BUCKET_NAME:
        from storages.backends.s3 import S3Storage
        return S3Storage(bucket_name=settings.R2_PRIVATE_BUCKET_NAME, default_acl="private", querystring_auth=True,
                         querystring_expire=60, custom_domain=None, file_overwrite=False)
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


def document_path(instance, filename):
    # Random name: the original filename (often the person's name) is not kept.
    from uuid import uuid4
    extension = {"application/pdf": "pdf", "image/png": "png"}.get(instance.content_type, "jpg")
    return f"verification/{instance.verification.landlord_id}/{uuid4().hex}.{extension}"


class LandlordVerification(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        VERIFIED = "verified", "Verified"
        NEEDS_MORE_INFO = "needs_more_info", "More information needed"
        REJECTED = "rejected", "Rejected"

    class IdType(models.TextChoices):
        NATIONAL_ID = "national_id", "National ID"
        PASSPORT = "passport", "Passport"
        ALIEN_ID = "alien_id", "Alien ID"
        COMPANY = "company_registration", "Company registration"

    class Relationship(models.TextChoices):
        OWNER = "owner", "I own the property"
        AGENT = "agent", "I am an agent authorised by the owner"
        CARETAKER = "caretaker", "I am the caretaker / property manager"
        COMPANY = "company", "A company I represent owns or manages it"

    landlord = models.ForeignKey("accounts.LandlordProfile", on_delete=models.CASCADE, related_name="verifications")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    legal_name = models.CharField(max_length=150)
    id_type = models.CharField(max_length=24, choices=IdType.choices)
    id_last4 = models.CharField(max_length=4)
    relationship = models.CharField(max_length=12, choices=Relationship.choices)
    agency_name = models.CharField(max_length=150, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_note = models.CharField(max_length=500, blank=True)
    documents_purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-submitted_at",)
        constraints = [
            models.UniqueConstraint(fields=("landlord",), condition=models.Q(status="pending"), name="one_pending_verification_per_landlord"),
        ]


class VerificationDocument(models.Model):
    class Kind(models.TextChoices):
        ID_FRONT = "id_front", "ID document (front)"
        ID_BACK = "id_back", "ID document (back)"
        OWNERSHIP = "ownership_proof", "Proof of ownership or management (e.g. title, lease, utility bill)"
        AUTHORITY = "authority_letter", "Owner's authority letter (agents and caretakers)"

    verification = models.ForeignKey(LandlordVerification, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    file = models.FileField(storage=private_storage, upload_to=document_path, max_length=255, blank=True)
    content_type = models.CharField(max_length=40)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)
