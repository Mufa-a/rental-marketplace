import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.exceptions import Conflict
from apps.core.models import AuditLog
from apps.notifications.services import notify

from .models import LandlordVerification, VerificationDocument

# Recognised by content, not by the filename or the browser-supplied type.
SIGNATURES = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"%PDF-", "application/pdf"))


def sniff_content_type(upload):
    head = upload.read(8)
    upload.seek(0)
    return next((kind for signature, kind in SIGNATURES if head.startswith(signature)), None)


def _audit(actor, action, obj, **metadata):
    AuditLog.objects.create(actor=actor, action=action, object_type=obj._meta.label, object_id=str(obj.pk), metadata=metadata)


@transaction.atomic
def submit(landlord_profile, *, user, data, files):
    """files: {kind: UploadedFile}. Raises ValidationError on bad input, Conflict if a review is open."""
    if landlord_profile.verifications.filter(status=LandlordVerification.Status.PENDING).exists():
        raise Conflict("Your verification is already being reviewed.", code="verification_pending")
    if landlord_profile.verifications.filter(status=LandlordVerification.Status.VERIFIED).exists():
        raise Conflict("Your account is already verified.", code="already_verified")
    if VerificationDocument.Kind.ID_FRONT not in files:
        raise ValidationError({"id_front": "Upload a clear photo or scan of your ID."})
    if data["relationship"] in ("agent", "caretaker") and VerificationDocument.Kind.AUTHORITY not in files:
        raise ValidationError({"authority_letter": "Agents and caretakers must upload the owner's authority letter."})
    checked = []
    for kind, upload in files.items():
        if upload.size > settings.VERIFICATION_DOCUMENT_MAX_BYTES:
            raise ValidationError({kind: "Each document must be 5 MB or smaller."})
        content_type = sniff_content_type(upload)
        if content_type is None:
            raise ValidationError({kind: "Upload a JPEG, PNG or PDF file."})
        digest = hashlib.sha256()
        for chunk in upload.chunks():
            digest.update(chunk)
        upload.seek(0)
        checked.append((kind, upload, content_type, digest.hexdigest()))
    verification = LandlordVerification.objects.create(landlord=landlord_profile, **data)
    for kind, upload, content_type, sha in checked:
        document = VerificationDocument(verification=verification, kind=kind, content_type=content_type, size=upload.size, sha256=sha)
        document.file.save("upload", upload, save=False)
        document.save()
    reused = VerificationDocument.objects.filter(sha256__in=[c[3] for c in checked]).exclude(verification__landlord=landlord_profile).exists()
    _audit(user, "verification.submitted", verification, documents=sorted(files), reused_document=reused)
    return verification


@transaction.atomic
def decide(verification_id, *, admin, decision, note=""):
    verification = LandlordVerification.objects.select_for_update().select_related("landlord__user").get(pk=verification_id)
    if verification.status != LandlordVerification.Status.PENDING:
        raise Conflict("This submission has already been decided.", code="already_decided")
    if decision not in (LandlordVerification.Status.VERIFIED, LandlordVerification.Status.REJECTED, LandlordVerification.Status.NEEDS_MORE_INFO):
        raise ValidationError({"decision": "Choose verified, rejected or needs_more_info."})
    if decision != LandlordVerification.Status.VERIFIED and not note.strip():
        raise ValidationError({"note": "Tell the landlord why, so they can fix it."})
    verification.status = decision
    verification.reviewed_by = admin
    verification.reviewed_at = timezone.now()
    verification.reviewer_note = note[:500]
    verification.save(update_fields=("status", "reviewed_by", "reviewed_at", "reviewer_note"))
    landlord = verification.landlord
    landlord.verification_tier = "standard" if decision == LandlordVerification.Status.VERIFIED else "basic"
    landlord.save(update_fields=("verification_tier",))
    _audit(admin, "verification.decided", verification, decision=decision)
    from apps.properties.views import _invalidate_public_listing_cache
    transaction.on_commit(_invalidate_public_listing_cache)
    message = {
        "verified": "Your landlord verification was approved. Your listings now show a verified-landlord badge.",
        "rejected": f"Your landlord verification was not approved: {note}",
        "needs_more_info": f"We need more information to verify you: {note} Please submit again from your profile.",
    }[decision]
    notify(recipient=landlord.user, event="verification.decided", dedupe_key=f"verification:{verification.pk}:decided",
           title="Verification update", message=message, link="/profile")
    return verification


def purge_expired_documents(now=None):
    """Delete document files for decisions older than the retention period. Keeps the decision record."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=settings.VERIFICATION_DOCUMENT_RETENTION_DAYS)
    purged = 0
    for verification in LandlordVerification.objects.filter(reviewed_at__lt=cutoff, documents_purged_at__isnull=True).exclude(status="pending"):
        for document in verification.documents.exclude(file=""):
            document.file.delete(save=False)
            document.file = ""
            document.save(update_fields=("file",))
            purged += 1
        verification.documents_purged_at = now
        verification.save(update_fields=("documents_purged_at",))
        _audit(None, "verification.documents_purged", verification)
    return purged
