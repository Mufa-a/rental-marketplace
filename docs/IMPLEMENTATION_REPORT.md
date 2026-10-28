# Implementation report — October 2026 hardening

Companion to `docs/AUDIT.md` (Phase 1 findings). Everything listed as done was exercised by automated tests and/or
an end-to-end browser run; anything not verified is listed under "Not done / needs the owner".

## Verification performed

| Check | Result |
|---|---|
| Backend tests, SQLite | **159 passed** (was 65) |
| Backend tests, PostgreSQL 16 + PostGIS 3 | **159 passed** |
| `makemigrations --check` | No missing migrations |
| Migrations on a database with existing data | Applied cleanly (audit-chain backfill, duplicate-request cleanup, payment receipt backfill) |
| Migration rollback | Every new migration reversed and re-applied on PostGIS with data intact |
| `manage.py check --deploy` (production settings) | One advisory left: HSTS preload (deliberately off) |
| `pip-audit` / `npm audit --omit=dev` | No known vulnerabilities |
| ESLint / `tsc --noEmit` / `next build` | Clean; first-load JS ≤ 122 kB per route |
| Browser end-to-end run (Playwright, dev and production builds) | Search, filters, pagination without duplicates, location pages, canonical redirects, structured data, tenant package purchase (simulator → server-confirmed), viewing request, duplicate refusal, landlord approval, contact release to both sides, timeline, notifications, admin console, mobile without horizontal scroll |
| Docker images + production compose stack | Built and run behind Caddy; migrations, SSR via internal API, Django admin static files, sitemap, scheduler jobs all verified |

Mutation checks confirmed the payment tests fail if callback confirmation or the duplicate-receipt guard is removed.

## Bugs fixed (each has a regression test)

1. Duplicate viewing requests for the same home each consumed a paid credit.
2. Dashboards were rate-limited on read (20 loads/hour returned HTTP 429).
3. A lost M-Pesa callback blocked further purchases permanently.
4. The M-Pesa callback URL lacked its trailing slash, so Django would redirect Safaricom's POST and lose it.
5. `distance_km` was always null; "Show more homes" repeated page one (cursor pagination ignored `?page=`).
6. Plain validation errors reached the browser as a bare list, hiding the real message.
7. Admin checks differed between endpoints (role alone was enough on listing endpoints).
8. OTP verification had no request throttle.
9. Found during this work: a landlord could cancel or reschedule a viewing *after* it happened, erasing it from
   referral attribution. Now a past viewing can only be resolved by an outcome report.
10. Server-rendered pages would have shared one public rate limit (single SSR IP); a sitemap and price page built
    without API access would have been frozen empty after each deploy.

## What was built

**Security & platform**: Django 5.2 LTS, DRF 3.18, Next.js 15.5 / React 19 (critical advisories closed);
self-hosted fonts; CSP and private-page headers; unified admin permission; tamper-evident audit log; production
start-up guards; CI workflow (`.github/workflows/ci.yml`); Dockerfiles, production compose with Caddy, backups.

**Search (Phase 3)**: county / town / estate / free-text search with relevance ranking, bathrooms, multiple
amenities, multiple home types, verified-only, move-in date, result counts, location suggestions, radius search with
working distances, trigram indexes, server-rendered and shareable search URLs, `/rentals/<county>/<town>/<estate>`
landing pages, canonical listing URLs. Unavailable, unmoderated, held, suspended-landlord and unconfirmed
(> 30 days) listings never appear publicly.

**Listings & landlords**: moderation statuses (approved / awaiting review / changes requested / rejected), optional
pre-moderation (`LISTINGS_REQUIRE_APPROVAL`), duplicate and reused-photo detection, "requires review" when a verified
property moves, view counting without visitor identifiers, landlord performance stats, mark occupied (closes
pending requests, returns credits, asks recent viewers whether they rented), landlord identity verification with
private documents.

**Bookings & anti-bypass (Phase 4)**: one service owns every transition; address and contacts released only after
approval; landlord cancel returns the credit; reschedule (max 3); booking timeline from the audit log; tenant can
report "I rented it" (including later, inside the 60-day attribution window); conflicting reports open a dispute and
a referral flag; marking a unit occupied after a viewing flags it and asks the tenant; admin rulings create the fee.
No tracking outside the platform.

**Payments**: configurable packages, fee rules and service prices per country; provider layer with STK Query
confirmation; reconciliation and timeouts; cancelled/refunded/disputed states; unique receipts; refunds; payment
history for users and admins; dev-only simulator. See `docs/PAYMENTS.md`.

**Admin (Phase 5)**: moderation queue, report handling (hide/suspend), landlord and property verification review,
referral reviews and rulings, payments with refunds and reconciliation, pricing editor, user suspension, audit-log
browser with chain verification, county/town/estate supply–demand report with "undersupplied" flag, trends, CSV
exports (masked phones, formula-injection safe).

**Notifications**: in-app inbox and bell for every event; SMS for important events with capped retries; optional
email. Events: requests, approvals/rejections, reschedules, cancellations, reminders, outcome prompts, listing
moderation, availability changes for saved homes, payment confirmations, verification decisions, referral outcomes.

**UX**: rebuilt home, listing, tenant, landlord, saved, notifications and admin pages on the existing design system;
packages and conditions shown before paying; payment status polled from the server; responsive layouts; light/dark
themes; accessible labels and focus states.

**Policies**: new Listing Rules and "Packages, Fees & Refunds" pages (live prices); privacy policy corrected for
contact release, verification and view counting.

## Migrations created

`core/0002_audit_hash_chain` · `notifications/0002_multichannel_inbox` ·
`payments/0004_configurable_pricing_and_payment_states` (seeds prices) · `properties/0007_marketplace_controls`
(pg_trgm indexes) · `properties/0008_media_content_hash` · `referrals/0002_marketplace_controls` ·
`verification/0001_initial` · `viewings/0004_marketplace_controls` (cancels pre-existing duplicate requests and
returns their credits). All reversible.

## Not done / needs the owner

* **Credentials and approvals**: Africa's Talking (production SMS), Safaricom Daraja go-live, R2 buckets (public +
  private), optional SMTP. Live payments are not activated and were tested only against a mocked provider and the
  simulator.
* **Legal**: legal entity details, DPO contact, retention periods and refund policy text placeholders; review by an
  advocate before publishing; Data Protection Act obligations listed in `docs/SECURITY.md`.
* **Not implemented**: self-service data export; TOTP for staff; refresh token in an HttpOnly cookie and CSP nonces;
  error monitoring (Sentry); WhatsApp notifications; credit expiry/per-region (sub-country) pricing (pricing is per
  country); automated M-Pesa refunds (B2C) — refunds are recorded after being made in the M-Pesa portal; switching an
  account between tenant and landlord roles.
* **Not tested**: real Daraja sandbox/production calls, real SMS delivery, real R2 uploads, load testing.
