from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import deliver_pending, notify
from apps.payments.services import reconcile_stale_payments
from apps.viewings.models import Viewing
from apps.viewings.services import expire_stale_requests


class Command(BaseCommand):
    help = ("Scheduled housekeeping (run every 15–60 minutes): reconcile pending payments, expire unanswered "
            "viewing requests, queue reminders and outcome prompts, and deliver pending SMS/email.")

    def handle(self, *args, **options):
        now = timezone.now()
        reconciled = reconcile_stale_payments()
        expired = expire_stale_requests(now)
        upcoming = Viewing.objects.filter(
            status=Viewing.Status.SCHEDULED, scheduled_at__gt=now, scheduled_at__lte=now + timedelta(hours=24),
        ).select_related("request__tenant__user", "request__unit__property__landlord__user")
        for viewing in upcoming:
            stamp = viewing.scheduled_at.isoformat()
            when = timezone.localtime(viewing.scheduled_at).strftime("%d %b, %I:%M %p")
            for user, role, link in ((viewing.request.tenant.user, "tenant", "/tenant"),
                                     (viewing.request.unit.property.landlord.user, "landlord", "/landlord?tab=viewings")):
                notify(recipient=user, event="viewing.reminder", dedupe_key=f"viewing:{viewing.pk}:reminder:{stamp}:{role}",
                       title="Viewing tomorrow", link=link,
                       message=f"Reminder: your viewing for {viewing.request.unit.title} is scheduled for {when}.")
        due_followups = Viewing.objects.filter(
            status=Viewing.Status.SCHEDULED, scheduled_at__lte=now - timedelta(hours=2), scheduled_at__gte=now - timedelta(days=2),
        ).select_related("request__tenant__user", "request__unit__property__landlord__user")
        for viewing in due_followups:
            stamp = viewing.scheduled_at.isoformat()
            for user, role, link in ((viewing.request.tenant.user, "tenant", "/tenant"),
                                     (viewing.request.unit.property.landlord.user, "landlord", "/landlord?tab=viewings")):
                notify(recipient=user, event="viewing.outcome_due", dedupe_key=f"viewing:{viewing.pk}:outcome-prompt:{stamp}:{role}",
                       title="How did the viewing go?", link=link,
                       message=f"How did the viewing for {viewing.request.unit.title} go? Sign in to report the outcome.")
        count = deliver_pending()
        pending = Notification.objects.filter(status=Notification.Status.PENDING).exclude(channel=Notification.Channel.IN_APP).count()
        self.stdout.write(self.style.SUCCESS(
            f"Payments reconciled: {reconciled or 'none'}. Requests expired: {expired}. "
            f"Sent {count} external notification(s); {pending} remain pending."))
