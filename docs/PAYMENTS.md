# Payments: how they work and how to go live

Nyumbani never collects rent or deposits. It takes three kinds of payment, all by M-Pesa STK Push (Daraja):

| Purpose | Who pays | Price comes from |
|---|---|---|
| Viewing package (credits) | Tenant | `ViewingPackage` rows, per country (admin → Packages & fees) |
| Success (referral) fee | Landlord, after a platform viewing becomes a tenancy | `ReferralFeeRule` rows: fixed or % of rent, by rent band, per country |
| Property verification (optional) | Landlord | `ServicePrice` row `property_verification` |

Launch prices are seeded by migration `payments/0004`: packages of 1/2/5/10 viewings for KES 50/100/150/250, the
previous referral fee bands (KES 1,500 / 2,500 / 4,000 / 6,000), and KES 2,000 property verification. They are
ordinary data: change them in the admin console. Every `Payment` row keeps the amount it was created with, so price
changes never alter past transactions.

## Lifecycle and safeguards

1. The browser asks the API to start a purchase with an idempotency key. The API creates one `Payment` (`pending`)
   per key (keys are scoped per user) and sends the STK prompt. Retries with the same key return the same payment
   and never send a second prompt. A second, different purchase is refused while a recent one is still pending.
2. Safaricom calls `MPESA_CALLBACK_URL/<MPESA_CALLBACK_TOKEN>/`. The token is compared in constant time; an optional
   IP allowlist (`MPESA_CALLBACK_ALLOWED_IPS`) can be added.
3. **The callback alone never grants anything.** With `MPESA_CONFIRM_CALLBACKS=True` (default) the API confirms the
   result with an STK Push Query before fulfilling. If Daraja contradicts the callback, the payment becomes
   `disputed` and nothing is granted. If Daraja cannot be reached, the payment stays `pending` and reconciliation
   finishes it.
4. Checks before fulfilment: amount equals the stored amount, a receipt number is present, and the receipt has not
   settled another payment (unique in the database).
5. Fulfilment is idempotent: credits are created once per payment, a fee is marked paid once, a property moves to
   "pending review" once.
6. Pending payments older than `PAYMENT_QUERY_AFTER_SECONDS` (90 s) are queried whenever the payer looks at them and
   by the scheduler every 10 minutes. With no final answer after `PAYMENT_TIMEOUT_MINUTES` (10), they become
   `failed` (reason `timeout`) so the user can try again. A success that arrives later is still honoured, because
   the money moved.
7. Statuses: `pending`, `successful`, `failed`, `cancelled` (payer dismissed the prompt, code 1032), `refunded`,
   `disputed` (needs a human). All transitions are written to the tamper-evident audit log.

The frontend only ever *displays* status it reads back from the API; there is no endpoint that lets a client set it.

## Refunds

Money is returned through Safaricom (reversal or B2C) by an authorised person. The administrator then records it in
the admin console (Payments → Record refund) with the reversal reference. Recording a refund removes unused credits
(it is refused while a credit from that package is reserved by an open request), waives a referral fee, or returns
a property to "unverified". The refund rules shown to users are on `/viewing-packages`.

## Going live checklist

1. **Daraja app**: create an app at developer.safaricom.co.ke with *Lipa Na M-Pesa Sandbox*; set
   `MPESA_ENV=sandbox`, the sandbox consumer key/secret, shortcode `174379` and the sandbox passkey. Test a purchase
   end to end with a sandbox number. Callbacks need a public HTTPS URL (your staging domain).
2. **Production approval**: apply for "Go Live" in the Daraja portal for your own paybill or till. Safaricom issues
   production credentials and the passkey by email.
3. Set `MPESA_ENV=production`, `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_SHORTCODE`, `MPESA_PASSKEY`.
   For a **till** (Buy Goods): `MPESA_TRANSACTION_TYPE=CustomerBuyGoodsOnline`, `MPESA_SHORTCODE` = store/head
   office number, `MPESA_PARTY_B` = till number. For a **paybill**: keep `CustomerPayBillOnline`.
4. `MPESA_CALLBACK_URL=https://<domain>/api/v1/payments/mpesa/callback` and a fresh random `MPESA_CALLBACK_TOKEN`
   (32+ characters). Never reuse the sandbox token.
5. Make one small real purchase with a staff phone, confirm the receipt appears in the admin Payments list, then
   record a refund for it to exercise that path.
6. Reconcile daily against the M-Pesa statement for the first weeks (admin Payments → Export CSV).

Until credentials are configured, starting a payment returns a clear "M-Pesa is not configured" message and records
a failed attempt; nothing is ever simulated in production (`PAYMENT_PROVIDER=simulator` is refused by
`config/settings/prod.py`).

## Local development

Set `PAYMENT_PROVIDER=simulator` with `DEBUG=True`. Prompts are not sent anywhere; complete the newest pending
payment with `python manage.py simulate_payment [payment_id] [--result success|cancelled|failed]`. The simulator
feeds the same callback-handling code as Safaricom, including the confirmation query.
