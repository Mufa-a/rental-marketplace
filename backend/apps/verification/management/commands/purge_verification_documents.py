from django.core.management.base import BaseCommand

from apps.verification.services import purge_expired_documents


class Command(BaseCommand):
    help = "Delete landlord verification documents past their retention period (run daily)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Deleted {purge_expired_documents()} verification document file(s)."))
