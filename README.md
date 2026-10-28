# Nyumbani rental marketplace

Nyumbani connects tenants and landlords in Kenya. Tenants search and save homes for free, buy viewing packages by
M-Pesa when they are ready, and request viewings. Landlords list homes for free, approve viewings, and pay a success
fee only when a tenant met through a platform viewing rents the home. The platform never collects rent or deposits.

| Document | What it covers |
|---|---|
| `docs/AUDIT.md` | Phase 1 audit of the original code |
| `docs/IMPLEMENTATION_REPORT.md` | What changed, how it was verified, what is still open |
| `docs/DEPLOYMENT.md` | Production deployment, releases, rollback, backups, Windows local setup |
| `docs/PAYMENTS.md` | Payment lifecycle, safeguards, M-Pesa go-live checklist |
| `docs/SECURITY.md` | Security review, remaining risks, Data Protection Act considerations |

## Stack

Django 5.2 LTS + Django REST Framework (`backend/`), Next.js 15 App Router + React 19 (`frontend/`), PostgreSQL 16 +
PostGIS + pg_trgm, Redis, Cloudflare R2 (photos and private verification documents), Africa's Talking (SMS/OTP),
Safaricom Daraja (M-Pesa STK Push).

## Run locally (Windows PowerShell)

Requirements: Python 3.12, Node.js 20.9+, Docker Desktop.

```powershell
docker compose up -d
```

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

In a second PowerShell window:

```powershell
Set-Location frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Open http://localhost:3000. Sign in with a phone number; with `DEBUG=True` and no SMS credentials the OTP prints in
the Django window. `seed_demo` (development only) creates listings across Kenya, landlords `+254700000100…107` and
tenants `+254700000200…202`. `createsuperuser` creates an admin who signs in the same way and uses `/admin`.

Payments use the development simulator by default (`PAYMENT_PROVIDER=simulator` in `backend/.env.example`). Buy a
package in the browser, then complete it with:

```powershell
python manage.py simulate_payment
```

Scheduled housekeeping (payment reconciliation, request expiry, reminders, SMS/email delivery) runs with
`python manage.py run_notifications`; in production the `scheduler` container runs it every 10 minutes.

## Tests and checks

```powershell
Set-Location backend
python -m pytest
python manage.py makemigrations --check --dry-run --settings=config.settings.test
```

To run the same suite against PostgreSQL + PostGIS (as CI does), point `DATABASE_URL` at a disposable database and
run `python -m pytest --ds=config.settings.test_postgres`.

```powershell
Set-Location frontend
npm run lint
npx tsc --noEmit
npm run build
```

CI (`.github/workflows/ci.yml`) runs all of the above plus `pip-audit` and `npm audit` on every pull request.

## API overview (`/api/v1/`)

* `auth/` — OTP request/verify, token refresh, logout, profile, consents, deletion requests.
* `properties/` — public `search/` (q, county, town, estate, rent, bedrooms, bathrooms, unit_type, amenities,
  furnishing, move_in_date, verified_only, latitude/longitude/radius_km, ordering), `locations/`, `listings/<slug>/`;
  landlord `mine/`, `mine/stats/`, units, availability, photos; tenant `saved/`.
* `viewings/` — requests (create, list, detail with timeline), approve/reject/cancel, reschedule/complete/outcome.
* `payments/` — `prices/`, `viewing-credits/`, `mine/`, `<id>/`, referral fee and verification payments, M-Pesa callback.
* `verification/landlord/` — landlord identity verification submission.
* `notifications/` — inbox, unread count, mark read.
* `trust/reports/` — report a listing or landlord.
* `admin/` — admin console API (staff admins only): moderation, verification, reports, referral rulings,
  payments/refunds, pricing, users, audit log, market reports, CSV exports.

Errors always use `{"error": {"code": "...", "message": "..."}}`.

## Configuration

All configuration is by environment variables; see `backend/.env.example`, `frontend/.env.local.example` and
`infra/production.env.example`. Never commit real values. Production refuses to start without a secret key,
explicit hosts, SMS credentials and private document storage, and refuses the payment simulator.
