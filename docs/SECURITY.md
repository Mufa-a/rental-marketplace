# Security and privacy review

Reviewed 2026-10-28 against the code in this repository. "Done" means implemented **and** covered by an automated
test or a documented manual check. This is an engineering review, not a penetration test or a legal opinion.

## Summary by area

| Area | Status | Details |
|---|---|---|
| Authentication | Done | Phone OTP: 6 digits, hashed, single use, 5-minute expiry, newer code invalidates older ones, 5 wrong tries lock the code for 15 min. Requests throttled per phone (3/15 min) and per network (60/h); verification throttled per phone across codes (10/15 min); the response is identical for new and existing numbers. Access token (15 min) kept only in page memory; refresh token (30 days, rotated, blacklisted on use) only in an HttpOnly, Secure, SameSite=Strict cookie scoped to `/api/v1/auth/`. Suspended accounts cannot sign in or refresh. **Administrators** also need a TOTP authenticator code; devices are enrolled only from the server, secrets are encrypted at rest, codes cannot be replayed. |
| Password storage / reset | N/A for users | Users have no passwords. Superusers created with `createsuperuser` sign in to Django admin with a password hashed by Django's default PBKDF2. |
| Role-based access | Done | One server-side rule for administrators (`apps/core/permissions.py`: active + staff + admin role). Every admin endpoint uses it; a parametrised test checks all admin endpoints reject anonymous, tenant, landlord, role-only and inactive users. Frontend role redirects are convenience only. |
| Tenant/landlord isolation | Done | Landlords reach only their own properties, units, media, requests and stats; tenants only their own requests, payments and saved homes; other users get 404. Contact details and the street address are released only to the two parties of an approved, uncancelled viewing (tested). |
| API permissions | Done | Default `IsAuthenticated`; public endpoints are explicitly `AllowAny` and read-only, except the payment callback (secret token + optional IP allowlist) and the view beacon. |
| Input validation | Done | DRF serializers on every write; realistic rent range; deposit sanity check; viewing times limited to the next 60 days; preferred times bounded; report detail ≤ 2,000 chars. |
| File uploads | Done | Listing photos: browser strips EXIF/GPS, direct PUT to R2 via 5-minute presigned URL scoped to `properties/<unit>/`, server HEAD-checks size ≤ 10 MB and image content type, ≤ 20 per listing, reused photos across landlords flag the listing. Verification documents: content-sniffed (JPEG/PNG/PDF magic bytes), ≤ 5 MB, random file names, private storage, admin-only audited download with `no-store` and a sandboxing CSP. Photos are also checked by their first bytes in storage; a disguised file is rejected and deleted. |
| Rate limiting | Done | OTP request/verify, viewing requests, reports, payment starts, verification uploads, public search. SSR uses a server-only token so visitors are limited individually rather than all sharing the renderer's IP. |
| CSRF | Done | The API uses bearer tokens in headers (no cookie auth), so cross-site requests cannot act as a user. Django admin keeps Django's CSRF protection and secure cookies in production. |
| XSS | Mostly done | React escapes output; the only raw HTML is the static theme script, JSON-LD with `<` escaped, and Leaflet popups built from escaped text. CSP blocks third-party scripts (except the SRI-pinned Leaflet build), objects, framing and foreign form posts. No credential is readable by page scripts (refresh token is HttpOnly; the access token is short-lived and in memory). *Gap*: `script-src 'unsafe-inline'` is needed by Next.js without nonce middleware. |
| SQL injection | Done | ORM throughout; the single raw fragment (PostGIS `ST_DWithin`) is parameterised. |
| Secrets | Done | All credentials from environment variables; `.env` files and `infra/production.env` are git-ignored; a scan of tracked files and history found no committed secrets. Production refuses to start with missing secrets, a short callback token or the payment simulator. |
| Database access & backups | Done (ops) | App connects as a non-superuser owner role; nightly `pg_dump` script with retention and off-site copy; restore procedure in `docs/DEPLOYMENT.md`. Enable disk encryption on the server. |
| Sensitive documents | Done | Only last 4 ID characters kept; documents private, admin-only, audited, purged after 90 days (configurable). |
| Payment verification | Done | Callback confirmed by STK Push Query before value is granted; amount check; unique receipts; idempotent fulfilment; reconciliation and timeout; refunds recorded with reason. 27 payment tests including mutation checks. |
| Duplicate transactions | Done | Per-user idempotency keys, one pending purchase at a time, unique receipts, one-time fulfilment. |
| Logging & errors | Done | Uniform JSON errors; no stack traces in production; request bodies (OTPs) not logged; tamper-evident, append-only audit log (hash chain + PostgreSQL trigger + `verify_audit_chain`). Optional Sentry (`SENTRY_DSN`) strips user identity, bodies, cookies, query strings and auth headers before sending. |
| Dependencies | Done | Django 5.2 LTS, DRF 3.18.3, Next.js 15.5.28 / React 19; `pip-audit` and `npm audit` report no known vulnerabilities; both run in CI. |
| Transport | Done | HTTPS via Caddy; HSTS (1 year, subdomains); secure cookies; strict referrer policy; `nosniff`; frame denial; private pages `no-store` + `noindex`. HSTS preload is deliberately not enabled (hard to reverse — opt in when ready). |

## Remaining risks (prioritised)

1. **`script-src 'unsafe-inline'`**: an XSS bug could run script in a signed-in page and act as the user while it
   is open (it can no longer steal a reusable credential). Next step: nonce-based CSP via Next.js middleware.
2. **Django admin** (`/<ADMIN_URL>`) uses Django's password login without a second factor. Keep the path secret,
   use strong superuser passwords, and restrict it by IP at the proxy; day-to-day work belongs in the MFA-protected
   console at `/admin`.
3. **Report auto-hide abuse**: three accounts can take a listing offline pending review. Accounts require a phone
   OTP and admins see report clusters; consider weighting reporters by history.
4. **New-account signals**: the "please accept the terms" prompt still tells a caller that a number is new
   (rate-limited per phone and per network).
5. **Frontend error monitoring** is not wired (only the API reports to Sentry).

## Kenya Data Protection Act, 2019 — engineering considerations

The platform processes personal data of Kenyan residents (phone numbers, names, identity document details for
landlords, location of homes, payment references). The following are implemented in code; **they do not by
themselves establish compliance**. The owner should confirm obligations with a qualified advocate.

* **Minimisation** (s.25): only last 4 ID characters; approximate public map pins; contact details released only
  for approved viewings; view counts without stored visitor identifiers; verification documents deleted after review.
* **Transparency and consent** (s.29–32): privacy policy describes what is collected and shared (updated for contact
  release, verification and view counting); versioned consent records; marketing consent separate and optional.
* **Data subject rights** (s.26, s.40): self-service download of one's own data ("Download my data" on the profile
  page, audited); profile correction in-app; deletion requests reviewed by an admin.
* **Security safeguards** (s.41): access control, encryption in transit, audit logging, restricted document access,
  backups.
* **Owner actions required**: determine whether registration with the Office of the Data Protection Commissioner is
  required under the 2021 Registration Regulations; appoint a data protection contact (fill `NEXT_PUBLIC_LEGAL_DPO_CONTACT`);
  publish retention periods (the `NEXT_PUBLIC_LEGAL_RETENTION_*` placeholders); if hosting outside Kenya, document the
  transfer safeguards (s.48–50); prepare a breach response plan (ODPC notification within 72 hours, s.43); consider a
  data protection impact assessment for identity verification (s.31); and have counsel review the draft legal pages
  before setting `NEXT_PUBLIC_LEGAL_STATUS=published`.
