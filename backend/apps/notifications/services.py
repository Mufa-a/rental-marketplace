from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from .models import Notification

# Events important enough to also send by SMS (cost per message). Everything
# else is in-app only. Email is added for every event when it is configured
# and the user has an address on their profile.
SMS_EVENTS = {
    "viewing.requested", "viewing.approved", "viewing.rejected", "viewing.cancelled",
    "viewing.rescheduled", "viewing.reminder", "viewing.expired", "viewing.outcome_due",
    "referral.fee_created", "referral.confirm_requested", "payment.successful",
    "verification.decided",
}
MAX_DELIVERY_ATTEMPTS = 5


def notify(*, recipient, event, dedupe_key, message, title="", link="", sms=None):
    """Record a notification for every applicable channel. Idempotent per dedupe_key."""
    channels = [Notification.Channel.IN_APP]
    if sms if sms is not None else event in SMS_EVENTS:
        channels.append(Notification.Channel.SMS)
    if settings.NOTIFICATION_EMAIL_ENABLED and recipient.email:
        channels.append(Notification.Channel.EMAIL)
    created = []
    for channel in channels:
        # SMS keys stay unsuffixed so rows queued before multi-channel support still deduplicate.
        key = dedupe_key if channel == Notification.Channel.SMS else f"{dedupe_key}:{channel}"
        defaults = {"recipient": recipient, "event": event, "channel": channel, "title": title[:140],
                    "message": message[:500], "link": link[:200]}
        if channel == Notification.Channel.IN_APP:
            defaults.update(status=Notification.Status.SENT, sent_at=timezone.now())
        created.append(Notification.objects.get_or_create(dedupe_key=key[:180], defaults=defaults)[0])
    return created


def queue_sms(*, recipient, event, dedupe_key, message, title="", link=""):
    """Backwards-compatible entry point: in-app plus SMS."""
    return notify(recipient=recipient, event=event, dedupe_key=dedupe_key, message=message, title=title, link=link, sms=True)


def _due(channel, limit):
    return (Notification.objects
            .filter(channel=channel, status__in=(Notification.Status.PENDING, Notification.Status.FAILED))
            .select_related("recipient").order_by("created_at")[:limit])


def _record_failure(notification, error):
    notification.status = (Notification.Status.ABANDONED if notification.attempt_count >= MAX_DELIVERY_ATTEMPTS
                           else Notification.Status.FAILED)
    notification.last_error = error[:255]


def deliver_pending(limit=100):
    """Attempt a bounded batch of external deliveries; failures retry up to MAX_DELIVERY_ATTEMPTS."""
    return _deliver_sms(limit) + _deliver_email(limit)


def _deliver_sms(limit):
    if not settings.AFRICASTALKING_API_KEY:
        return 0
    import africastalking

    africastalking.initialize(settings.AFRICASTALKING_USERNAME, settings.AFRICASTALKING_API_KEY)
    sent = 0
    for notification in _due(Notification.Channel.SMS, limit):
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
            _record_failure(notification, f"SMS delivery failed ({type(exc).__name__}).")
        notification.save(update_fields=("attempt_count", "status", "provider_reference", "last_error", "sent_at"))
    return sent


def _deliver_email(limit):
    if not settings.NOTIFICATION_EMAIL_ENABLED:
        return 0
    sent = 0
    for notification in _due(Notification.Channel.EMAIL, limit):
        notification.attempt_count += 1
        if not notification.recipient.email:
            _record_failure(notification, "Recipient has no email address.")
            notification.status = Notification.Status.ABANDONED
        else:
            try:
                link = f"\n\n{settings.FRONTEND_BASE_URL}{notification.link}" if notification.link else ""
                send_mail(notification.title or "Nyumbani update", notification.message + link,
                          settings.DEFAULT_FROM_EMAIL, [notification.recipient.email])
                notification.status = Notification.Status.SENT
                notification.last_error = ""
                notification.sent_at = timezone.now()
                sent += 1
            except Exception as exc:
                _record_failure(notification, f"Email delivery failed ({type(exc).__name__}).")
        notification.save(update_fields=("attempt_count", "status", "last_error", "sent_at"))
    return sent


def inbox(user):
    return Notification.objects.filter(recipient=user, channel=Notification.Channel.IN_APP)


def unread_count(user):
    return inbox(user).filter(read_at__isnull=True).count()


def mark_read(user, ids=None):
    rows = inbox(user).filter(read_at__isnull=True)
    if ids is not None:
        rows = rows.filter(Q(pk__in=ids))
    return rows.update(read_at=timezone.now())
