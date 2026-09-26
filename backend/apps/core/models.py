"""
Shared base models and the append-only AuditLog. Import AuditLog from here
in every app that needs to record a state-changing action.
"""
from django.db import models


class AuditLog(models.Model):
    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["object_type", "object_id"])]
