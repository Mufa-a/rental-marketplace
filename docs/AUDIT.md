# Nyumbani — Phase 1 repository audit

Audit date: 2026-10-28. Branch audited: `claude/zen-bardeen-qd7hqo` (HEAD `711e025`, which merges `feature/dashboard-verification-uploads` into the earlier marketplace overhaul).

Everything below was checked against the code, and where marked **(verified)** it was reproduced with a test or a command. Nothing is listed as missing until the repository was searched for it.

## 1. What exists today

**Stack.** Django 5.0.6 + Django REST Framework + SimpleJWT API (`backend/`), Next.js 14.2.5 App Router frontend (`frontend/`), PostgreSQL 16 + PostGIS, Redis (cache and throttling), Cloudflare R2 (photos), Africa's Talking (SMS/OTP), Safaricom Daraja STK Push (M-Pesa). `docker-compose.yml` runs only Postgres and Redis; there is no application container, CI workflow or deployment manifest.

**Baseline health (verified).** 65 backend tests pass on SQLite and on PostgreSQL 16 + PostGIS 3. `makemigrations --check` reports no drift; all migrations apply to an empty PostGIS database. `tsc --noEmit` and `next build` succeed.

| Area | Implemented |
|---|---|
| Auth | Phone OTP sign-up/sign-in (hashed single-use codes, 5-minute TTL, 5-attempt lockout, per-phone request throttle), JWT access/refresh with rotation and blacklist, logout, profile edit, consent records, account-deletion requests reviewed by admins. Admin role cannot be self-assigned. |
| Listings | Property → Unit model, amenities, furnishing, R2 presigned photo uploads with server-side HEAD validation and browser EXIF stripping, landlord isolation (`_owned_property/_owned_unit`), 30-day availability reconfirmation, delete blocked when history exists, moderation hold. |
| Search | Public cursor-paginated search: city/area substring, rent range, bedrooms, type, furnishing, one amenity, move-in date, PostGIS radius + distance sort, 60-second Redis cache, approximate map pins. |
| Tenants | Saved homes, viewing requests (max 3 active), cancel, outcome reporting, credit wallet and M-Pesa bundle purchase. |
| Landlords | Dashboard (overview / homes / viewings / payments tabs), create/edit/pause/delete units, approve with schedule or decline, report outcome, pay success fee, pay for property verification. |
| Bookings | ViewingRequest → Viewing → Outcome (one per party); disagreement opens a Dispute; landlord "rented" creates ReferralAttribution + ReferralFee, unpublishes the unit and auto-sends an STK push. Credits reserved on request, consumed on approval, restored on decline/cancel/expiry. |
| Payments | Payment rows with idempotency key, STK push, token-in-URL callback, amount check, purposes: viewing credits / referral fee / verification fee. |
| Trust | Listing reports (one open per user per listing), auto-hide at N serious reports, Django-admin actions to dismiss/hide/suspend, account restrictions. |
| Notifications | SMS outbox with dedupe keys; `run_notifications` command expires stale requests, queues reminders and outcome prompts. |
| Admin | Read-only React dashboard (metrics, focus queue, area supply/demand, activity, users, viewing requests). All moderation is done in Django admin. AuditLog written for most state changes. |
| Legal/SEO | Terms, privacy, cookies, data-protection, copyright pages (owner details still placeholders), metadata, canonical on listing pages, sitemap, robots, JSON-LD, security headers. |

## 2. Findings, highest priority first

### Critical — fix before any production traffic

1. **Next.js 14.2.5 has critical published advisories (verified with `npm audit`)**, including unauthenticated remote code execution in the image optimisation endpoint (the app enables it via `images.remotePatterns`), a middleware authorisation bypass and several cache-poisoning and DoS issues. Fixed only in Next 15.5.28+/16.x.
2. **Django 5.0.6 is end-of-life** (security support ended April 2025) and is missing two years of security releases. Move to Django 5.2 LTS.
3. **A lost M-Pesa callback blocks a user permanently (verified).** Pending payments never expire or get reconciled, and a pending bundle/verification payment blocks any new purchase with HTTP 409 — forever. There is no STK Push Query reconciliation, no `cancelled` status (Safaricom result 1032), and the M-Pesa receipt number is not stored uniquely.
4. **Duplicate viewing requests (verified).** A tenant can request the same home repeatedly; each request reserves another paid credit and notifies the landlord again.
5. **Landlord/tenant dashboards are rate-limited to 20 page loads per hour (verified).** The `viewing_request` throttle (20/hour) is attached to the list `GET` as well as `POST`; landlords receive HTTP 429 and an empty dashboard.

### High

6. **Callback trust.** Payment success is decided solely from the callback body, authenticated by a token in the URL. There is no server-to-server confirmation with Daraja before value (credits/verification/fee) is granted.
7. **"Show more homes" repeats results (verified).** The frontend sends `?page=N`, but the API uses cursor pagination and ignores it, so page 1 is appended again.
8. **`distance_km` is always `null` (verified on SQLite and PostGIS).** The serializer expects a GeoDjango `Distance` object; the annotation is a float.
9. **Approved tenants never receive the address or a contact.** The address is (correctly) private, but it is never revealed after approval, so a viewing cannot actually happen through the platform — which pushes both sides to swap numbers off-platform.
10. **Tenant cannot report "I rented it" in the UI** (the API supports it). This removes the main independent signal for referral attribution.
11. **No referral protection after a viewing.** If a landlord marks a unit occupied shortly after a viewing without reporting the outcome, nothing is flagged. Disputes can only be closed by editing rows in Django admin, and a ruling never creates the fee.
12. **AuditLog is editable and unchained.** Anyone with DB or Django-admin access can change booking/referral history without trace.
13. **OTP verify endpoint has no request throttle** (only the per-code 5-attempt lock).
14. **Prices are hard-coded**: bundles `{1:50, 3:100, 5:150, 10:250}`, referral fee tiers, KSh 2,000 verification fee. No per-country/region pricing, no admin management.

### Medium

15. Search is limited: no county or free-text query, no bathrooms filter, a single amenity, no relevance sort, no result count; `icontains` on area/city has no supporting index.
16. No listing moderation status or duplicate-listing check; new listings go live with no review option.
17. Landlord verification (identity) does not exist — `apps/verification` is an empty stub. Only paid property verification exists, and it is decided in Django admin.
18. Notifications are SMS-only; there is no in-app inbox. Failed SMS rows are retried forever (cost risk).
19. The admin dashboard is read-only: no moderation queue, verification review, report handling, payment history, refunds, package management, audit-log viewer or exports.
20. Admin checks are inconsistent: the dashboard requires `role=admin` **and** `is_staff`; listing endpoints accept `role=admin` alone.
21. Report reasons do not cover fake photos, unavailable properties or misleading prices explicitly.
22. No listing-performance data for landlords (views are not counted).
23. Frontend stores JWTs in `localStorage`, and there is no Content-Security-Policy, so any XSS would expose tokens.

### Low

24. `otp/request` returns `new_account`, which allows phone-number enumeration (rate-limited per phone).
25. Listing URLs differ between cards (`nairobi%20cbd`) and the sitemap (`nairobi-cbd`), so the canonical URL and the sitemap URL disagree for multi-word areas.
26. JSON-LD always uses `Apartment` with an `InStock` offer regardless of home type.
27. `SENTRY_DSN` is configured but nothing reads it. Celery is configured but unused (cron runs `run_notifications`).

## 3. Deployment blockers

* Critical framework upgrades (items 1–2).
* No application Dockerfiles, CI pipeline, backup policy or rollback runbook.
* M-Pesa and SMS credentials, an R2 bucket, a public callback URL and the legal-entity details for the legal pages must be supplied by the owner.
* `run_notifications` (and, after this work, payment reconciliation) must be scheduled.

## 4. Plan

Phase 2 fixes items 1–5, 7, 8, 13 and 20. Phase 4 delivers configurable packages and fees, payment reconciliation and hardening, address/contact reveal on approval, tenant rental confirmation, occupied-after-viewing flags, admin dispute rulings and a tamper-evident audit chain. Phase 3 delivers the search, moderation-status, duplicate-check and listing-analytics work. Phase 5 delivers in-app notifications, landlord verification with private documents and an actionable admin dashboard with exports. Phase 6 covers tests, CI and the deployment/rollback runbook. Results are recorded in `docs/IMPLEMENTATION_REPORT.md`.
