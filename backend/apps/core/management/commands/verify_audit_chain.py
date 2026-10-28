from django.core.management.base import BaseCommand, CommandError

from apps.core.models import verify_audit_chain


class Command(BaseCommand):
    help = "Recompute the audit-log hash chain and report the first entry that was altered or removed."

    def handle(self, *args, **options):
        checked, broken = verify_audit_chain()
        if broken is not None:
            raise CommandError(f"Audit chain broken at entry {broken} (after {checked} valid entries).")
        self.stdout.write(self.style.SUCCESS(f"Audit chain intact: {checked} entries verified."))
