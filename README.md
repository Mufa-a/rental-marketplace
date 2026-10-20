# Nyumbani rental marketplace

Nyumbani connects tenants and landlords in Kenya. Tenants can browse available homes for free, search nearby listings, buy M-Pesa viewing bundles, request viewings, and manage their profile. Landlords can publish and pause units, upload photos to Cloudflare R2, approve or decline viewing requests, and pay a success fee only when they report that a viewing led to a rental.

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
npm test
npm run build
```

`.github/workflows/ci.yml` runs all of the above (plus Docker image builds) on every push to `main` and every pull request. `npm run lint` currently reports a few warnings (plain `<img>` tags, a font link, two effect dependency lists); it fails only on errors.

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
- `/api/v1/properties/units/{id}/media/` and `/media/presign/` register photos and a video uploaded directly to R2; `DELETE /api/v1/properties/media/{id}/` removes one. A home can have up to 20 photos (JPEG, PNG or WebP, 10 MB each) and one optional video (MP4, WebM or MOV, 100 MB); a new video replaces the old one. The API returns photos in `media` and the video separately in `video`, so a video never reaches an `<img>`. Because a presigned upload cannot cap size or type, registration checks the stored file and deletes anything that fails; removed or replaced files are deleted from the bucket. Limits are `MEDIA_MAX_PHOTOS_PER_UNIT`, `MEDIA_MAX_IMAGE_BYTES` and `MEDIA_MAX_VIDEO_BYTES` (the frontend limits in `frontend/lib/mediaUpload.ts` must match). The browser re-encodes photos to remove EXIF/GPS, but **videos are uploaded as recorded and may carry location data**, so landlords are told to switch off location tagging. Configure `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, and `R2_PUBLIC_BASE_URL` to enable it, and allow `PUT` with a `Content-Type` header from your site's origin in the bucket's CORS rules. Run `python manage.py migrate` after upgrading (migration `0007` adds the video type).
- `POST /api/v1/properties/units/{id}/availability/` is the landlord availability confirmation action. It records the confirmation time; `available` cannot be changed through ordinary listing edits.
- `/api/v1/viewings/requests/` lets tenants request viewings. Landlords can approve and schedule or decline their own requests; the tenant and landlord can report outcomes.
- Tenants buy viewing-request credits through M-Pesa bundles: 1 for KSh 50, 3 for KSh 100, 5 for KSh 150, or 10 for KSh 250. Browsing stays free. A request reserves a credit; landlord decline, tenant cancellation before approval, or unanswered expiry returns it.
- The landlord success fee is created as soon as the landlord reports a viewing as rented; the tenant's report is not required. That report is final: it unpublishes the unit, closes the unit's other pending viewing requests (returning their credits), creates the fee and sends an M-Pesa prompt to the landlord's registered phone, and the dashboard asks the landlord to confirm before sending it. Otherwise, if the two sides report different outcomes, a dispute is opened for an administrator; a landlord's "rented" report always takes precedence over that. Fees carry a due date (seven days); `run_notifications` sends one overdue reminder and the admin dashboard lists overdue fees. `POST /api/v1/payments/referral-fees/{fee_id}/pay/` and `POST /api/v1/payments/viewing-credits/` start M-Pesa STK Pushes; Safaricom callbacks are accepted at the configured callback URL plus `MPESA_CALLBACK_TOKEN`.
- Viewing request/approval and fee events are saved to a retryable SMS outbox. Run `python manage.py run_notifications` from `backend` hourly (Windows Task Scheduler or cron) to send queued SMS and create 24-hour viewing reminders. Without Africa’s Talking credentials the messages remain queued.
- `/robots.txt` and `/sitemap.xml` are generated by Next.js. Set `NEXT_PUBLIC_SITE_URL` in `frontend/.env.local` to the public canonical origin.

API validation and permission errors use the documented `{ "error": { "code": "...", "message": "..." } }` response format. OTP throttling is phone-scoped; viewing requests are limited to three concurrent active requests per tenant.

## Environment and deployment

Copy `backend/.env.example` to `backend/.env` for local development. Do not commit real secrets. Production should use `DJANGO_SETTINGS_MODULE=config.settings.prod`, a strong `DJANGO_SECRET_KEY`, explicit `ALLOWED_HOSTS`, PostgreSQL and Redis URLs, Africa’s Talking credentials, and R2 credentials where photo uploads are required.

The Daraja request and callback code is present, but live tenant bundles and landlord success-fee payments need Safaricom credentials, an approved merchant setup, a public HTTPS callback URL, and a strong callback token. Africa's Talking and Cloudflare R2 likewise remain disabled until their real credentials and bucket settings are supplied. Set a restricted `NEXT_PUBLIC_MAPTILER_KEY` for the commercial map tile service before production; the OpenStreetMap fallback is for local preview.

### Running it in containers

`docker-compose.prod.yml` runs PostGIS, Redis, a one-shot `migrate` job, the API (gunicorn), a notifications worker and the Next.js site:

```powershell
Copy-Item backend\.env.example backend\.env   # real secrets; DEBUG=False; production ALLOWED_HOSTS
# .env.prod: POSTGRES_ADMIN_PASSWORD, APP_DB_PASSWORD, NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_SITE_URL
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

- **TLS is not included.** Put a reverse proxy in front of ports 8000 (API) and 3000 (site). Production settings redirect plain HTTP to HTTPS and trust `X-Forwarded-Proto` from it.
- **The `worker` service must stay running.** It runs `run_notifications` every hour (`NOTIFICATION_INTERVAL_SECONDS` to change it). SMS delivery, viewing and overdue-fee reminders, and the seven-day expiry of unanswered viewing requests all depend on it.
- `NEXT_PUBLIC_*` values are baked into the site at build time, so changing one means rebuilding the `frontend` image. Add any `NEXT_PUBLIC_LEGAL_*` values you need as build args in the frontend Dockerfile and compose file.
- The API healthcheck sends the first `ALLOWED_HOSTS` entry as its `Host` header, so list your real API hostname first.
- The images were written without being built in the authoring environment; the first CI run (`docker` job) is the real test of them.

### Trust and safety settings

- `REPORT_AUTO_HIDE_THRESHOLD` (default 3): open reports for a serious reason that take a listing offline for review.
- `REPORT_MIN_ACCOUNT_AGE_HOURS` (default 24): only reports from phone-verified accounts at least this old count toward that threshold. Other reports still appear in the admin queue.
- The frontend admin dashboard lists open reports and properties awaiting verification (read-only). Resolve reports and verify or reject properties from Django admin, where each action is recorded against the acting administrator.

See [`docs/payment-tools-and-costs.md`](docs/payment-tools-and-costs.md) for current bundle pricing, provider costs, assumptions, and launch setup items.
