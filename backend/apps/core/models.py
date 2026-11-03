"""
Shared base models and the append-only AuditLog. Import AuditLog from here
in every app that needs to record a state-changing action.

AuditLog is tamper-evident: every entry stores the hash of the previous entry
and a SHA-256 over its own content, forming a chain. Editing or deleting any
historical row (booking events, approvals, outcomes, payments, referral
rulings) breaks the chain, which `python manage.py verify_audit_chain`
detects. On PostgreSQL a trigger additionally rejects UPDATE/DELETE of
anything except the nullable actor link (needed when an account is deleted).
"""
import hashlib
import json

from django.db import connection, models, transaction
from django.utils import timezone

GENESIS_HASH = "0" * 64


def audit_entry_hash(prev_hash, *, actor_ref, action, object_type, object_id, metadata, created_at):
    payload = json.dumps(
        {
            "actor": actor_ref, "action": action, "object_type": object_type,
            "object_id": str(object_id), "metadata": metadata, "created_at": created_at.isoformat(),
        },
        sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(f"{prev_hash}:{payload}".encode()).hexdigest()


class AuditLog(models.Model):
    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    # Immutable snapshot of the actor id at write time; survives account deletion.
    actor_ref = models.CharField(max_length=32, blank=True)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    prev_hash = models.CharField(max_length=64, blank=True, editable=False)
    entry_hash = models.CharField(max_length=64, blank=True, editable=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["action", "-created_at"], name="core_audit_action_idx"),
        ]

    def compute_hash(self, prev_hash):
        return audit_entry_hash(
            prev_hash, actor_ref=self.actor_ref, action=self.action, object_type=self.object_type,
            object_id=self.object_id, metadata=self.metadata, created_at=self.created_at,
        )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Audit log entries are append-only.")
        with transaction.atomic():
            if connection.vendor == "postgresql":
                # Serialise appends so every entry links to the one committed before it.
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(hashtext('core_auditlog_chain'))")
            self.actor_ref = str(self.actor_id) if self.actor_id else ""
            self.created_at = self.created_at or timezone.now()
            # Hash exactly what the JSON column will return (tuples become lists, etc.).
            self.metadata = json.loads(json.dumps(self.metadata or {}, default=str))
            last = AuditLog.objects.order_by("-id").values_list("entry_hash", flat=True).first()
            self.prev_hash = last or GENESIS_HASH
            self.entry_hash = self.compute_hash(self.prev_hash)
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit log entries are append-only.")


def verify_audit_chain():
    """Return (checked_count, first_broken_id or None)."""
    previous = GENESIS_HASH
    checked = 0
    for entry in AuditLog.objects.order_by("id").iterator(chunk_size=2000):
        if entry.prev_hash != previous or entry.compute_hash(previous) != entry.entry_hash:
            return checked, entry.pk
        previous = entry.entry_hash
        checked += 1
    return checked, None
