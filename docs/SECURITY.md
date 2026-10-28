# Security and privacy review

Reviewed 2026-10-28 against the code in this repository. "Done" means implemented **and** covered by an automated
test or a documented manual check. This is an engineering review, not a penetration test or a legal opinion.

## Summary by area

| Area | Status | Details |
|---|---|---|
| Authentication | Done | Phone OTP: 6 digits, hashed, single use, 5-minute expiry, newer code invalidates older ones, 5 wrong tries lock the code for 15 min. Requests throttled per phone (3/15 min) and per network (60/h); verification throttled per phone across codes (10/15 min). JWT access 15 min, refresh 30 days with rotation and blacklist; logout blacklists the refresh token. Suspended accounts cannot sign in again by OTP. |
| Password storage / reset | N/A for users | Users have no passwords. Superusers created with `createsuperuser` sign in to Django admin with a password hashed by Django's default PBKDF2. |
| Role-based access | Done | One server-side rule for administrators (`apps/core/permissions.py`: active + staff + admin role). Every admin endpoint uses it; a parametrised test checks all admin endpoints reject anonymous, tenant, landlord, role-only and inactive users. Frontend role redirects are convenience only. |
| Tenant/landlord isolation | Done | Landlords reach only their own properties, units, media, requests and stats; tenants only their own requests, payments and saved homes; other users get 404. Contact details and the street address are released only to the two parties of an approved, uncancelled viewing (tested). |
| API permissions | Done | Default `IsAuthenticated`; public endpoints are explicitly `AllowAny` and read-only, except the payment callback (secret token + optional IP allowlist) and the view beacon. |
| Input validation | Done | DRF serializers on every write; realistic rent range; deposit sanity check; viewing times limited to the next 60 days; preferred times bounded; report detail ≤ 2,000 chars. |
| File uploads | Mostly done | Listing photos: browser strips EXIF/GPS, direct PUT to R2 via 5-minute presigned URL scoped to `properties/<unit>/`, server HEAD-checks size ≤ 10 MB and image content type, ≤ 20 per listing, reused photos across landlords flag the listing. Verification documents: content-sniffed (JPEG/PNG/PDF magic bytes), ≤ 5 MB, random file names, private storage, admin-only audited download with `no-store` and a sandboxing CSP. *Gap*: photo content type is the uploader's declared type (served from the separate R2 origin, so no script runs on the site's origin). |
| Rate limiting | Done | OTP request/verify, viewing requests, reports, payment starts, verification uploads, public search. SSR uses a server-only token so visitors are limited individually rather than all sharing the renderer's IP. |
| CSRF | Done | The API uses bearer tokens in headers (no cookie auth), so cross-site requests cannot act as a user. Django admin keeps Django's CSRF protection and secure cookies in production. |
| XSS | Mostly done | React escapes output; the only raw HTML is the static theme script, JSON-LD with `<` escaped, and Leaflet popups built from escaped text. CSP blocks third-party scripts (except the SRI-pinned Leaflet build), objects, framing and foreign form posts. *Gap*: `script-src 'unsafe-inline'` is needed by Next.js without nonce middleware. |
| SQL injection | Done | ORM throughout; the single raw fragment (PostGIS `ST_DWithin`) is parameterised. |
| Secrets | Done | All credentials from environment variables; `.env` files and `infra/production.env` are git-ignored; a scan of tracked files and history found no committed secrets. Production refuses to start with missing secrets, a short callback token or the payment simulator. |
| Database access & backups | Done (ops) | App connects as a non-superuser owner role; nightly `pg_dump` script with retention and off-site copy; restore procedure in `docs/DEPLOYMENT.md`. Enable disk encryption on the server. |
| Sensitive documents | Done | Only last 4 ID characters kept; documents private, admin-only, audited, purged after 90 days (configurable). |
| Payment verification | Done | Callback confirmed by STK Push Query before value is granted; amount check; unique receipts; idempotent fulfilment; reconciliation and timeout; refunds recorded with reason. 27 payment tests including mutation checks. |
| Duplicate transactions | Done | Per-user idempotency keys, one pending purchase at a time, unique receipts, one-time fulfilment. |
| Logging & errors | Done | Uniform JSON errors; no stack traces in production; request bodies (OTPs) not logged; tamper-evident, append-only audit log (hash chain + PostgreSQL trigger + `verify_audit_chain`). |
| Dependencies | Done | Django 5.2 LTS, DRF 3.18.3, Next.js 15.5.28 / React 19; `pip-audit` and `npm audit` report no known vulnerabilities; both run in CI. |
| Transport | Done | HTTPS via Caddy; HSTS (1 year, subdomains); secure cookies; strict referrer policy; `nosniff`; frame denial; private pages `no-store` + `noindex`. HSTS preload is deliberately not enabled (hard to reverse — opt in when ready). |

## Remaining risks (prioritised)

1. **Tokens in `localStorage`** combined with `'unsafe-inline'` scripts: an XSS bug would expose tokens. Mitigated by
   React escaping, CSP and short access-token life. Next step: move the refresh token to an `HttpOnly`,
   `SameSite=Strict` cookie and add CSP nonces.
2. **SMS-only admin sign-in** is exposed to SIM-swap fraud. Add TOTP (authenticator app) for staff accounts and
   restrict Django admin by IP.
3. **Account enumeration**: `otp/request` reveals whether a number is new (rate-limited per phone and network).
4. **Listing photo type is not content-sniffed** server-side (see File uploads).
5. **No error monitoring service** is wired in (`SENTRY_DSN` is reserved). Add Sentry or similar with PII scrubbing.
6. **Abuse of report auto-hide**: three accounts can take a listing offline pending review. Accounts require a phone
   OTP, and admins see report clusters; consider weighting reporters by history.

## Kenya Data Protection Act, 2019 — engineering considerations

The platform processes personal data of Kenyan residents (phone numbers, names, identity document details for
landlords, location of homes, payment references). The following are implemented in code; **they do not by
themselves establish compliance**. The owner should confirm obligations with a qualified advocate.

* **Minimisation** (s.25): only last 4 ID characters; approximate public map pins; contact details released only
  for approved viewings; view counts without stored visitor identifiers; verification documents deleted after review.
* **Transparency and consent** (s.29–32): privacy policy describes what is collected and shared (updated for contact
  release, verification and view counting); versioned consent records; marketing consent separate and optional.
* **Data subject rights** (s.26, s.40): profile correction in-app; deletion requests reviewed by an admin. *Not yet
  automated*: a self-service export of a user's data (access/portability requests must be handled manually).
* **Security safeguards** (s.41): access control, encryption in transit, audit logging, restricted document access,
  backups.
* **Owner actions required**: determine whether registration with the Office of the Data Protection Commissioner is
  required under the 2021 Registration Regulations; appoint a data protection contact (fill `NEXT_PUBLIC_LEGAL_DPO_CONTACT`);
  publish retention periods (the `NEXT_PUBLIC_LEGAL_RETENTION_*` placeholders); if hosting outside Kenya, document the
  transfer safeguards (s.48–50); prepare a breach response plan (ODPC notification within 72 hours, s.43); consider a
  data protection impact assessment for identity verification (s.31); and have counsel review the draft legal pages
  before setting `NEXT_PUBLIC_LEGAL_STATUS=published`.
