# Deploying Nyumbani

This runbook covers a single-server deployment with Docker Compose: Caddy (automatic HTTPS) in front of the
Next.js site and the Django API on one domain, plus PostgreSQL/PostGIS, Redis and a scheduler. It was tested
end to end on 2026-10-28: images built, migrations applied to a fresh database and rolled back, and every public
route served through Caddy.

## 1. What you need

| Item | Notes |
|---|---|
| A Linux server (2 vCPU / 4 GB RAM is plenty to start) with Docker Engine + Compose v2 | Ports 80 and 443 open |
| A domain whose A/AAAA record points at the server | Caddy obtains the TLS certificate automatically |
| Africa's Talking account (username + API key) and an approved sender ID | Required: production refuses to start without SMS, because sign-in is by OTP |
| Safaricom Daraja app (consumer key/secret), shortcode and passkey | See `docs/PAYMENTS.md`. Without them, purchases fail cleanly with "M-Pesa is not configured" |
| Cloudflare R2: one **public** bucket for listing photos, one **private** bucket for verification documents, and an API token | The private bucket must have no public access. Or set `ALLOW_LOCAL_PRIVATE_MEDIA=True` to keep documents on the encrypted server volume |
| Optional: SMTP credentials | Turns on email notifications |
| Legal details for the legal pages (`NEXT_PUBLIC_LEGAL_*`) | Placeholders show until they are provided |

## 2. First deployment

```bash
git clone https://github.com/Mufa-a/rental-marketplace.git /srv/nyumbani && cd /srv/nyumbani
cp infra/production.env.example infra/production.env && chmod 600 infra/production.env
# Edit infra/production.env: domain, secrets (generate each one), Africa's Talking, M-Pesa, R2.
export RELEASE=$(git rev-parse --short HEAD)
docker compose -f docker-compose.prod.yml --env-file infra/production.env build
docker compose -f docker-compose.prod.yml --env-file infra/production.env up -d db redis
docker compose -f docker-compose.prod.yml --env-file infra/production.env run --rm backend python manage.py migrate
docker compose -f docker-compose.prod.yml --env-file infra/production.env run --rm backend python manage.py createsuperuser
docker compose -f docker-compose.prod.yml --env-file infra/production.env up -d
```

`createsuperuser` asks for a phone number: that account signs in on the website with an SMS code and gets the
admin console at `/admin`. Django's own admin is at `/<ADMIN_URL>` (a non-default path you choose).

Check: `https://your-domain/healthz/` returns `{"status": "ok"}`, the home page lists homes, and
`docker compose ... logs scheduler` shows a run every 10 minutes.

### Settings that must be right

* `ALLOWED_HOSTS` includes your domain **and** `backend` (the Next.js server calls the API by that name).
* `INTERNAL_API_TOKEN` is set (the compose file passes it to the frontend too). Without it, all server-side page
  renders share one public rate limit.
* `MPESA_CALLBACK_URL=https://your-domain/api/v1/payments/mpesa/callback` and a 32+ character `MPESA_CALLBACK_TOKEN`.
* `NUM_PROXIES=1` (Caddy) so rate limits apply per visitor, not per proxy.
* `REFERRAL_ATTRIBUTION_DAYS` is used by both images; the frontend shows it on the legal pages.
* Production refuses to boot with the payment simulator, a short callback token, missing SMS credentials,
  `ALLOWED_HOSTS=*` or no private document storage.

## 3. Releasing a new version

1. Read the release's migrations (`git diff <old>..<new> -- '*/migrations/*'`). Every migration in this repository
   is reversible; note the last migration of each app **before** upgrading:
   `docker compose ... run --rm backend python manage.py showmigrations | grep '\[X\]' > /tmp/pre-release-migrations.txt`
2. Back up the database (section 5).
3. Build the new images with a new tag: `export RELEASE=$(git rev-parse --short HEAD)` then `docker compose ... build`.
4. Apply migrations: `docker compose ... run --rm backend python manage.py migrate`.
5. Switch traffic: `docker compose ... up -d` (containers are replaced one by one; downtime is a few seconds).
6. Smoke test: `/healthz/`, home page search, sign in, admin console overview.

## 4. Rolling back

* **Code only** (no new migrations): `export RELEASE=<previous tag>` and `docker compose ... up -d --no-build`.
  Keep at least the previous image tag on the server (`docker image ls nyumbani-*`).
* **With migrations**: first migrate back to the numbers you recorded in step 1, using the *new* image (it contains
  the reverse operations), e.g. `docker compose ... run --rm backend python manage.py migrate viewings 0003`.
  Then start the previous images as above. Rollback of every migration added in the 2026-10 hardening work was
  tested and preserves data.
* **Last resort**: restore the pre-release backup (section 5). Payments confirmed after the backup must then be
  re-checked against the M-Pesa statement.

## 5. Backups and restore

`infra/backup.sh` writes a compressed `pg_dump` (and local verification documents, if used) and keeps 14 days.
Run it nightly from cron and copy the files off the server (`BACKUP_REMOTE` with rclone to a private bucket).

Restore into a fresh stack:

```bash
docker compose -f docker-compose.prod.yml --env-file infra/production.env up -d db
docker compose -f docker-compose.prod.yml --env-file infra/production.env exec -T db \
  pg_restore -U postgres -d rental_marketplace --clean --if-exists --no-owner < backups/db-YYYYMMDDTHHMMSSZ.dump
docker compose -f docker-compose.prod.yml --env-file infra/production.env run --rm backend python manage.py verify_audit_chain
```

Test a restore at least monthly. `verify_audit_chain` after a restore confirms booking and payment history was not
altered.

## 6. Scheduled work

The `scheduler` service runs every 10 minutes: `run_notifications` (reconciles pending M-Pesa payments, expires
unanswered viewing requests, queues reminders and outcome prompts, sends SMS/email with capped retries). Daily it
also runs `purge_verification_documents` and `verify_audit_chain`. A broken chain makes that command exit non-zero —
alert on it (`docker compose ... logs scheduler | grep "Audit chain broken"`).

## 7. Monitoring and logs

All services log to stdout (`docker compose ... logs -f backend`). Request bodies are never logged (they can contain
OTP codes). Watch: 5xx responses in Caddy logs, `payments_needing_review` and `referral_reviews` on the admin
overview, and SMS rows stuck in `failed`/`abandoned` in Django admin. `SENTRY_DSN` is reserved but no SDK is
installed yet (see the implementation report).

## 8. Local development (Windows PowerShell)

```powershell
docker compose up -d
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

In a second window:

```powershell
Set-Location frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

With `PAYMENT_PROVIDER=simulator` (the `.env.example` default), buy a viewing package in the browser, then complete
it with `python manage.py simulate_payment` (add `--result cancelled` or `--result failed` to try those paths).
OTP codes print in the Django window.
