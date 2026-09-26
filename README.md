# Nyumbani rental marketplace

Nyumbani connects tenants and landlords in Kenya. Tenants can browse available homes for free, search nearby listings, buy M-Pesa viewing bundles, request viewings, and manage their profile. Landlords can publish and pause units, upload photos to Cloudflare R2, approve or decline viewing requests, and pay a success fee only when both parties confirm a rental.

## Requirements

- Python 3.12
- Node.js 20 or newer
- Docker Desktop (for a local PostgreSQL and Redis instance)

The app stores property locations as PostGIS geography points for radius search. Local development uses the configured PostgreSQL/PostGIS service in Docker.

## Run locally on Windows PowerShell

From the repository root, start the database and Redis:

```powershell
docker compose up -d
```

Start Django:

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API runs at `http://localhost:8000`; Django admin runs at `http://localhost:8000/admin`. The separate frontend admin dashboard is at `http://localhost:3000/admin` and requires an active staff account with the admin role. Sign in through the frontend OTP page; `createsuperuser` creates the required staff/admin account.

Start Next.js in a second PowerShell window:

```powershell
Set-Location frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

The site runs at `http://localhost:3000`. Set `NEXT_PUBLIC_API_BASE_URL` in `.env.local` if Django runs at another URL.

## Tests and checks

Backend tests use in-memory SQLite and a stub SMS transport, so no running database or SMS credentials are needed:

```powershell
Set-Location backend
python -m pytest
python manage.py check --settings=config.settings.test
python manage.py makemigrations --check --dry-run --settings=config.settings.test
```

Frontend checks:

```powershell
Set-Location frontend
npx tsc --noEmit
npm run lint
npm run build
```

## Authentication and local OTP

Signup and sign-in share a phone-based, one-time-code flow:

- `POST /api/v1/auth/otp/request/` accepts a Kenyan number and optional `tenant` or `landlord` role. Public signup cannot assign admin access.
- `POST /api/v1/auth/otp/verify/` validates a hashed, single-use code that expires after five minutes and returns short-lived access and rotating refresh tokens.
- `POST /api/v1/auth/token/refresh/` refreshes the access token.
- `GET, PATCH /api/v1/auth/me/` reads and updates the signed-in user’s profile.
- `POST /api/v1/auth/logout/` blacklists the signed-in user’s refresh token.

With `DEBUG=True` and no Africa’s Talking credentials, Django prints the OTP to its local terminal. Production refuses to start without a Django secret, explicit allowed hosts, and SMS credentials; it never prints OTPs.

## Listings and viewings

- `GET /api/v1/properties/search/` provides public paginated search with city, area, rent range, bedrooms, home type, amenity, and sort filters.
- Radius search accepts `latitude`, `longitude`, and `radius_km`; PostGIS uses the indexed geography column. Search is cursor-paginated and briefly cached in Redis. Available listings disappear from search and details after 30 days without landlord reconfirmation.
- The public home page has an opt-in “Homes near me” search. Browser location is used for radius filtering, homes are ordered by distance, and public map pins are approximate. New landlord listings need coordinates; the map uses `NEXT_PUBLIC_MAPTILER_KEY` in production. OpenStreetMap tiles are the local preview fallback.
- `GET, POST /api/v1/properties/saved/` and `DELETE /api/v1/properties/saved/{unit_id}/` let tenants maintain a private saved-homes list.
- `GET /api/v1/properties/listings/{slug}/` returns a published, available unit.
- `/api/v1/properties/mine/`, `/api/v1/properties/{id}/units/`, and the unit detail endpoints let landlords manage only their own listings. Admins have cross-listing access.
- `/api/v1/properties/units/{id}/media/` and `/media/presign/` register photos uploaded directly to R2. The browser re-encodes photos to remove EXIF/GPS metadata. Configure `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, and `R2_PUBLIC_BASE_URL` to enable it.
- `POST /api/v1/properties/units/{id}/availability/` is the landlord availability confirmation action. It records the confirmation time; `available` cannot be changed through ordinary listing edits.
- `/api/v1/viewings/requests/` lets tenants request viewings. Landlords can approve and schedule or decline their own requests; the tenant and landlord can report outcomes.
- Tenants buy viewing-request credits through M-Pesa bundles: 1 for KSh 50, 3 for KSh 100, 5 for KSh 150, or 10 for KSh 250. Browsing stays free. A request reserves a credit; landlord decline, tenant cancellation before approval, or unanswered expiry returns it.
- After both parties confirm a rental, the landlord success fee is created. `POST /api/v1/payments/referral-fees/{fee_id}/pay/` and `POST /api/v1/payments/viewing-credits/` start M-Pesa STK Pushes; Safaricom callbacks are accepted at the configured callback URL plus `MPESA_CALLBACK_TOKEN`.
- Viewing request/approval and fee events are saved to a retryable SMS outbox. Run `python manage.py run_notifications` from `backend` hourly (Windows Task Scheduler or cron) to send queued SMS and create 24-hour viewing reminders. Without Africa’s Talking credentials the messages remain queued.
- `/robots.txt` and `/sitemap.xml` are generated by Next.js. Set `NEXT_PUBLIC_SITE_URL` in `frontend/.env.local` to the public canonical origin.

API validation and permission errors use the documented `{ "error": { "code": "...", "message": "..." } }` response format. OTP throttling is phone-scoped; viewing requests are limited to three concurrent active requests per tenant.

## Environment and deployment

Copy `backend/.env.example` to `backend/.env` for local development. Do not commit real secrets. Production should use `DJANGO_SETTINGS_MODULE=config.settings.prod`, a strong `DJANGO_SECRET_KEY`, explicit `ALLOWED_HOSTS`, PostgreSQL and Redis URLs, Africa’s Talking credentials, and R2 credentials where photo uploads are required.

The Daraja request and callback code is present, but live tenant bundles and landlord success-fee payments need Safaricom credentials, an approved merchant setup, a public HTTPS callback URL, and a strong callback token. Africa's Talking and Cloudflare R2 likewise remain disabled until their real credentials and bucket settings are supplied. Set a restricted `NEXT_PUBLIC_MAPTILER_KEY` for the commercial map tile service before production; the OpenStreetMap fallback is for local preview.

See [`docs/payment-tools-and-costs.md`](docs/payment-tools-and-costs.md) for current bundle pricing, provider costs, assumptions, and launch setup items.
