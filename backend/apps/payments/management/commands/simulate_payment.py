"""Complete a simulator payment locally. Refuses to run unless DEBUG is on and PAYMENT_PROVIDER=simulator."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.payments.models import Payment
from apps.payments.services import handle_callback

RESULT_CODES = {"success": 0, "cancelled": 1032, "failed": 1}


class Command(BaseCommand):
    help = "Development only: deliver a simulated M-Pesa callback for a pending simulator payment."

    def add_arguments(self, parser):
        parser.add_argument("payment_id", type=int, nargs="?", help="Defaults to the newest pending simulator payment.")
        parser.add_argument("--result", choices=sorted(RESULT_CODES), default="success")

    def handle(self, *args, payment_id=None, result="success", **options):
        if not settings.DEBUG or settings.PAYMENT_PROVIDER != "simulator":
            raise CommandError("simulate_payment only runs with DEBUG=True and PAYMENT_PROVIDER=simulator.")
        payments = Payment.objects.filter(provider="simulator", status=Payment.Status.PENDING)
        payment = payments.filter(pk=payment_id).first() if payment_id else payments.order_by("-created_at").first()
        if payment is None:
            raise CommandError("No pending simulator payment found.")
        payment.provider_payload = {**(payment.provider_payload or {}), "simulated_result": result}
        payment.save(update_fields=("provider_payload", "updated_at"))
        code = RESULT_CODES[result]
        body = {"Body": {"stkCallback": {"CheckoutRequestID": payment.provider_reference, "ResultCode": code, "ResultDesc": f"Simulated {result}"}}}
        if code == 0:
            body["Body"]["stkCallback"]["CallbackMetadata"] = {"Item": [
                {"Name": "Amount", "Value": payment.amount},
                {"Name": "MpesaReceiptNumber", "Value": f"SIM{payment.pk:07d}"},
                {"Name": "PhoneNumber", "Value": payment.phone_number.lstrip("+")},
            ]}
        payment = handle_callback(body)
        self.stdout.write(self.style.SUCCESS(f"Payment {payment.pk} is now {payment.status}."))
