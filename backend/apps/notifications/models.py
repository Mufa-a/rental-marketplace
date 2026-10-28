"""Durable, multi-channel notification outbox with deduplication.

Every event creates an in-app row (shown in the user's notification inbox) and,
for events that warrant it, rows for external channels (SMS today; email when
configured). External rows are delivered by `run_notifications` with bounded
retries; in-app rows are delivered the moment they are written.
"""
from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed (will retry)"
        ABANDONED = "abandoned", "Failed (gave up)"

    class Channel(models.TextChoices):
        IN_APP = "in_app", "In-app"
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.SMS)
    event = models.CharField(max_length=60)
    dedupe_key = models.CharField(max_length=180, unique=True)
    title = models.CharField(max_length=140, blank=True)
    message = models.CharField(max_length=500)
    # Relative frontend path, e.g. "/tenant#request-12". Never an external URL.
    link = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    provider_reference = models.CharField(max_length=100, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("recipient", "channel", "-created_at"), name="notif_inbox_idx"),
        ]
