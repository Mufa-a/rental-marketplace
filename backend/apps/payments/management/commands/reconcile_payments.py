from django.core.management.base import BaseCommand

from apps.payments.services import reconcile_stale_payments


class Command(BaseCommand):
    help = "Ask the payment provider for the final state of pending payments that never received a callback."

    def handle(self, *args, **options):
        results = reconcile_stale_payments()
        summary = ", ".join(f"{count} {status}" for status, count in sorted(results.items())) or "nothing to reconcile"
        self.stdout.write(self.style.SUCCESS(f"Reconciled payments: {summary}."))
