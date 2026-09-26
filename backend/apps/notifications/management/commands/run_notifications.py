from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.notifications.models import Notification
from apps.notifications.services import deliver_pending, queue_sms
from apps.core.models import AuditLog
from apps.viewings.models import Viewing
from apps.viewings.models import ViewingRequest


class Command(BaseCommand):
    help = "Queue due viewing reminders and deliver pending marketplace SMS messages."

    def handle(self, *args, **options):
        now = timezone.now()
        expired = ViewingRequest.objects.filter(
            status=ViewingRequest.Status.PENDING,
            created_at__lt=now - timedelta(days=7),
        ).select_related("tenant__user", "unit__property__landlord__user")
        for item in expired:
            item.status = ViewingRequest.Status.EXPIRED
            item.save(update_fields=("status", "updated_at"))
            from apps.payments.services import settle_viewing_credit
            settle_viewing_credit(item, restore=True)
            AuditLog.objects.create(actor=None, action="viewing_request.expired", object_type=item._meta.label, object_id=str(item.pk))
            queue_sms(recipient=item.tenant.user, event="viewing.expired", dedupe_key=f"viewing-request:{item.pk}:expired:tenant", message=f"Your viewing request for {item.unit.title} expired because it did not receive a reply in time.")
            queue_sms(recipient=item.unit.property.landlord.user, event="viewing.expired", dedupe_key=f"viewing-request:{item.pk}:expired:landlord", message=f"A viewing request for {item.unit.title} expired after seven days without a response.")
        upcoming = Viewing.objects.filter(
            status=Viewing.Status.SCHEDULED,
            scheduled_at__gt=now,
            scheduled_at__lte=now + timedelta(hours=24),
        ).select_related("request__tenant__user", "request__unit__property__landlord__user")
        for viewing in upcoming:
            stamp = viewing.scheduled_at.isoformat()
            parties = (
                (viewing.request.tenant.user, "tenant"),
                (viewing.request.unit.property.landlord.user, "landlord"),
            )
            for user, role in parties:
                queue_sms(
                    recipient=user, event="viewing.reminder",
                    dedupe_key=f"viewing:{viewing.pk}:reminder:{stamp}:{role}",
                    message=f"Reminder: your rental viewing is scheduled for {timezone.localtime(viewing.scheduled_at).strftime('%d %b, %I:%M %p')}.",
                )
        due_followups = Viewing.objects.filter(
            status=Viewing.Status.SCHEDULED,
            scheduled_at__lte=now - timedelta(hours=2),
            scheduled_at__gte=now - timedelta(days=2),
        ).select_related("request__tenant__user", "request__unit__property__landlord__user")
        for viewing in due_followups:
            stamp = viewing.scheduled_at.isoformat()
            for user, role in ((viewing.request.tenant.user, "tenant"), (viewing.request.unit.property.landlord.user, "landlord")):
                queue_sms(recipient=user, event="viewing.outcome_due", dedupe_key=f"viewing:{viewing.pk}:outcome-prompt:{stamp}:{role}", message="How did the viewing go? Sign in and mark it complete to report the outcome.")
        count = deliver_pending()
        pending = Notification.objects.filter(status=Notification.Status.PENDING).count()
        self.stdout.write(self.style.SUCCESS(f"Sent {count} SMS notification(s); {pending} remain pending."))
