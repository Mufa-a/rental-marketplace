from django.conf import settings
from django.utils import timezone

from .models import Notification


def queue_sms(*, recipient, event, dedupe_key, message):
    return Notification.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={"recipient": recipient, "event": event, "message": message[:500]},
    )[0]


def deliver_pending(limit=100):
    """Attempt a bounded batch; failed rows stay retryable and deduplicated."""
    if not settings.AFRICASTALKING_API_KEY:
        return 0
    import africastalking

    africastalking.initialize(settings.AFRICASTALKING_USERNAME, settings.AFRICASTALKING_API_KEY)
    sent = 0
    rows = Notification.objects.filter(status__in=(Notification.Status.PENDING, Notification.Status.FAILED)).select_related("recipient").order_by("created_at")[:limit]
    for notification in rows:
        notification.attempt_count += 1
        try:
            response = africastalking.SMS.send(notification.message, [notification.recipient.phone_number])
            recipients = response.get("SMSMessageData", {}).get("Recipients", [])
            if not recipients or any(row.get("status") != "Success" for row in recipients):
                raise RuntimeError("Africa's Talking did not confirm SMS delivery.")
            notification.status = Notification.Status.SENT
            notification.provider_reference = str(recipients[0].get("messageId", ""))[:100]
            notification.last_error = ""
            notification.sent_at = timezone.now()
            sent += 1
        except Exception as exc:
            notification.status = Notification.Status.FAILED
            notification.last_error = f"SMS delivery failed ({type(exc).__name__})."
        notification.save(update_fields=("attempt_count", "status", "provider_reference", "last_error", "sent_at"))
    return sent
