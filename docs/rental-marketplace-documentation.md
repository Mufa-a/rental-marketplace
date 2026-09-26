# Rental Marketplace — Full Project Documentation

*Kenyan tenant–landlord marketplace. Consolidates the business model, data model, and technical architecture agreed on so far, plus build-stage detail (testing, deployment, environment config) not previously written down. Companion to `kenya-rental-marketplace-strategy.md` (business strategy, A–AB) and `glassmorphism-search-screen.html` (visual direction) — this document is the engineering source of truth.*

---

## 1. Project Overview

A marketplace connecting tenants, landlords, and eventually property managers/agents in Kenya. The platform earns money by successfully introducing a tenant to a landlord — not by collecting rent. Core product bets: unit-level (not building-level) listings, mandatory outcome reporting on every viewing, and a landlord success-fee revenue model so listing carries zero risk for supply-side users.

**Roles (3 at MVP):** Tenant, Landlord (a property manager/agent slots into this same role, managing units on behalf of multiple owners), Admin. No sub-tiers of Admin until team size actually requires it.

---

## 2. Business Model (Summary)

- **Tenants:** free to browse, search, and save; M-Pesa bundles pay for sending viewing requests. Credits are restored for declined, cancelled-before-approval, or expired requests.
- **Landlords:** free to list and get verified; pay a tiered success fee (KSh 1,500–6,000 by rent band) when they report a successful rental. The listing is taken down and an STK Push is sent to their registered phone.
- **Coast pay-per-view model:** run only as a bounded, labeled pilot with instant credit restoration on landlord-side failure — not the default architecture, given its resemblance to a known Kenyan scam pattern (pay-before-you-see house-listing fraud).
- Full reasoning, unit economics, risk table, and launch tactics: see the strategy document.

---

## 3. Roles & Permissions

| Action | Tenant | Landlord | Admin |
|---|---|---|---|
| Browse/search | ✅ (no account) | ✅ | ✅ |
| Request viewing | ✅ | — | ✅ |
| Approve/reject/reschedule viewing | — | ✅ (own units) | ✅ (any) |
| Create/edit unit | — | ✅ (own) | ✅ (any) |
| Report outcome | ✅ (own viewings) | ✅ (own units) | ✅ |
| Verify landlord/property | — | — | ✅ |
| Issue refund / resolve dispute | — | — | ✅ |
| View audit log | — | — | ✅ |
| Suspend account | — | — | ✅ |

Enforced server-side via DRF permission classes, never trusted from the client.

---

## 4. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript | SSR for SEO on listing pages; type safety matters for the viewing state machine |
| Backend | Django + Django REST Framework | Fast to build verification/admin-heavy workflows; mature RBAC and ORM |
| Database | PostgreSQL + PostGIS | Relational integrity for fee/outcome logic; PostGIS for radius search |
| Object storage | Cloudflare R2 (S3-compatible) | Zero egress fees — matters once serving many property photos to mobile users |
| CDN | Cloudflare | Fronts R2 and edge-caches public pages; also does edge rate limiting |
| Cache / broker | Redis (Upstash for a serverless-friendly managed option) | Search-result caching, DRF throttle storage, Celery broker |
| Async jobs | Celery + Celery beat | OTP sending, outcome reminder nudges, freshness decay |
| SMS/OTP | Africa's Talking (WhatsApp Business API as a cheaper fallback) | Local delivery reliability and cost |
| Payments | M-Pesa Daraja API (STK push) | Landlord success fees and tenant viewing-credit bundles; no rent collection or payout leg |
| Search (later, if needed) | Meilisearch or Typesense | Lightweight, self-hostable upgrade path from Postgres full-text search |

---

## 5. Repository Structure

```
rental-marketplace/                  (monorepo — one place to clone and run)
├── backend/
│   ├── config/
│   │   ├── settings/{base,dev,prod}.py
│   │   ├── urls.py
│   │   └── celery.py
│   ├── apps/
│   │   ├── accounts/        User, TenantProfile, LandlordProfile, OTP, JWT auth
│   │   ├── properties/      Property, Unit, PropertyMedia, Amenity
│   │   ├── viewings/        ViewingRequest, Viewing, Outcome, state machine
│   │   ├── referrals/       ReferralAttribution, ReferralFee
│   │   ├── payments/        Payment, M-Pesa Daraja integration
│   │   ├── verification/    landlord/property verification workflow
│   │   ├── trust/           Report, Dispute, AccountRestriction, reliability scoring
│   │   ├── notifications/   SMS/WhatsApp/email sending
│   │   └── core/            AuditLog, base models, custom permissions/throttles
│   ├── api/                 DRF routers, versioned (/api/v1/)
│   ├── tests/
│   └── manage.py
├── frontend/
│   ├── app/
│   │   ├── (public)/        landing, search, /listings/[area]/[unit-slug]
│   │   ├── (tenant)/        dashboard, saved, viewings, profile
│   │   └── (landlord)/      dashboard, properties, requests, fees
│   ├── components/ui/       glass-card, glass-input, badges — the design system
│   ├── lib/                 api client, auth utils
│   └── styles/tokens.css
├── infra/                   env templates, deploy config
└── docs/                    this file, the strategy doc, design references
```

**Admin panel:** staff admins use the separate Next.js `/admin` dashboard to track marketplace activity, rentals, landlord success fees, tenant viewing bundles, and M-Pesa payment statuses. Django admin at `/admin` remains available for back-office data management.

---

## 6. Data Model

```
User ──< TenantProfile / LandlordProfile
LandlordProfile ──< Property ──< Unit ──< PropertyMedia
Unit ──< Amenity (M2M)
TenantProfile ──< SavedProperty, SearchPreference
TenantProfile ──< ViewingRequest >── Unit
ViewingRequest ──1:1── Viewing (once approved + scheduled)
Viewing ──< Outcome (one per party: tenant_outcome, landlord_outcome)
Viewing ──1:1── ReferralAttribution ──< ReferralFee ──< Payment
Verification (polymorphic: Landlord, Property, or Unit)
Report, Dispute (reference a Viewing/Listing + involved Users)
Notification (polymorphic target)
AuditLog (append-only, references any entity)
AccountRestriction ──> User
```

**Viewing state machine:**

```
REQUESTED → PENDING_LANDLORD
  → APPROVED → SCHEDULED → COMPLETED → OUTCOME_PENDING
        → RENTED / DID_NOT_RENT / STILL_DECIDING / DISPUTED
  → REJECTED
  → RESCHEDULED → back to SCHEDULED
  → EXPIRED (landlord silence beyond 48–72h)
  → CANCELLED
  → NO_SHOW
```

**Referral attribution window: 60 days** from the viewing date — long enough for a realistic Kenyan rental decision cycle, short enough to avoid wrongly attributing unrelated later transactions.

---

## 7. Authentication & OTP

- Phone number is the primary identity anchor (more reliable than email in this market).
- 6-digit OTP via Africa's Talking, 5-minute expiry, stored hashed, single-use.
- Rate-limited at the source: max 3 OTP requests per phone per 15 minutes.
- 5 failed verification attempts → 15-minute lockout on that phone.
- JWT (SimpleJWT): short-lived access token + rotating refresh token, blacklisted on logout.
- Role assigned at registration (tenant vs landlord flow), checked server-side on every request.

---

## 8. Security

- RBAC via DRF permission classes tied to the 3 roles.
- DRF serializers validate every input; viewing-outcome and fee-triggering endpoints get extra scrutiny since that's where fee-dodging or fake-outcome manipulation would happen.
- File uploads: presigned upload URLs direct to R2 (never through the Django server), type/size validated, EXIF metadata stripped before storage (prevents GPS leakage from a landlord's phone photo).
- M-Pesa callbacks use a deployment-configured, unguessable callback token in the URL and process each checkout only once. Before production, add source-IP allowlisting or provider-side transaction verification where available.
- Admin accounts require 2FA — the admin panel can issue refunds and rule on disputes, making it the highest-value target.
- HTTPS/HSTS everywhere; secrets in environment variables or a secrets manager, never committed.
- Append-only `AuditLog` on every state-changing action.

---

## 9. Caching & Rate Limiting

- Redis-backed DRF throttles (not in-memory — won't share state once you run multiple app instances).
- Tiered throttles: tight on OTP requests and login, moderate on viewing-request creation (anti-spam lever), generous on public search.
- Cloudflare edge rate-limiting rules as a first line of defense before traffic reaches Django.
- Redis caches public search results for 60 seconds and invalidates them when listings, media, or availability changes. Search and detail endpoints hide availability older than 30 days.
- Property detail pages are good CDN-edge cache candidates (short TTL + purge-on-update).

---

## 10. Database & Search Indexing

- Composite Postgres indexes on common filter combos: city + bedrooms + rent range + availability.
- PostGIS GIST index for radius search — required at any real scale; naive lat/long comparison won't hold up.
- Postgres GIN/tsvector for amenity/description text search at MVP scale; migrate to Meilisearch/Typesense if search volume outgrows it.
- Standard FK indexes (Django auto-creates these) plus explicit indexes on high-lookup fields: phone number (OTP), viewing ID.

---

## 11. SEO Strategy (Expanded)

SEO matters more here than in most marketplaces because organic search is how a tenant relocating to a city they don't live in yet finds you — that's your highest-intent, lowest-cost-to-acquire user.

**Technical SEO**
- SSR/SSG on every unit page via Next.js — unit-level URLs, not building-level, not query strings: `/listings/nairobi/westlands/green-apartments-a03`, not `/listing?id=4821`.
- `schema.org` structured data (JSON-LD) on every unit page so Google can surface price, bedrooms, and availability directly in search results:
```json
{
  "@context": "https://schema.org",
  "@type": "Apartment",
  "name": "Green Apartments — Unit A03",
  "numberOfRooms": 1,
  "address": {
    "@type": "PostalAddress",
    "addressLocality": "Westlands",
    "addressRegion": "Nairobi County",
    "addressCountry": "KE"
  },
  "offers": {
    "@type": "Offer",
    "price": "26000",
    "priceCurrency": "KES",
    "availability": "https://schema.org/InStock"
  }
}
```
- Auto-generated, auto-updating `sitemap.xml` reflecting current listings; unavailable/removed units return a proper `404`/`410`, never a silently-broken "unavailable" page (search engines penalize soft-404s).
- `robots.txt` disallowing tenant/landlord dashboard routes and API endpoints from crawling, while explicitly allowing `/listings/` and city/estate landing pages.
- Canonical tags on every listing page to prevent duplicate-content penalties if a unit is ever reachable via more than one URL pattern (e.g. filtered search result vs direct link).

**On-page SEO**
- Unique, template-generated `<title>`/meta description per unit page pulling real attributes: *"1 Bedroom in Westlands, Nairobi — KSh 26,000/month | [Brand]"* — not a generic template repeated across every page.
- Descriptive `alt` text on every photo (bedroom, kitchen, exterior — pulled from the media type field, not left blank).
- Internal linking: unit pages link to their area landing page and to 2–3 similar units nearby, which both helps users and spreads link equity across the site.

**Content SEO**
- Dedicated, SSR'd **city/estate landing pages** (`/nairobi/westlands`, `/mombasa/nyali`) that aggregate available units in that area — these are what rank for the actual long-tail searches people run ("houses to rent in Westlands", "1 bedroom Nyali"), independent of any single listing's churn.
- A lightweight content section (moving checklists, area guides, "what to know before renting in Kilimani") targets informational long-tail queries and builds topical authority — low effort, compounding payoff, fits the "relocation mode" use case directly.

**Performance SEO**
- Core Web Vitals matter directly for ranking: Next.js `<Image>` component + Cloudflare CDN for fast image delivery, especially important given most Kenyan traffic is mobile on variable network quality.
- Mobile-first indexing is the default now — the glassmorphism UI's responsive behavior (already built) is not just a UX nice-to-have, it's an SEO requirement.

**Off-page / ongoing**
- Google Search Console set up from day one — submit the sitemap, monitor indexing coverage and Core Web Vitals reports.
- The freshness system does double duty for SEO: recently-confirmed listings and regularly-updated area pages signal content recency, which Google factors into ranking.
- As verified landlords grow, encourage them to link back from their own social pages/business listings — natural backlink growth from a real supply-side network, not paid link schemes.

---

## 12. Payments (M-Pesa)

- Daraja API, STK push, for the landlord referral fee only — no tenant payments, no payout leg (you're only ever collecting, never disbursing).
- The API starts a landlord fee collection request and accepts the checkout callback under `MPESA_CALLBACK_URL` plus `MPESA_CALLBACK_TOKEN`. Set `MPESA_ENV=sandbox` until end-to-end sandbox reconciliation is complete.
- Payment states: `PENDING → SUCCESSFUL / FAILED`, with `REFUNDED` and `DISPUTED` as branches off `SUCCESSFUL` when a dispute ruling reverses a fee.
- Idempotency keys on every callback; reconciliation job to catch any STK push that succeeded on Safaricom's side but didn't get recorded due to a dropped callback.

---

## 13. API Conventions

- Versioned from day one: `/api/v1/...` — avoids breaking the frontend when v2 changes land later.
- Consistent error shape across all endpoints: `{ "error": { "code": "...", "message": "..." } }`, never a bare string or stack trace.
- Cursor-based pagination on list endpoints (search results, viewing history) — offset pagination degrades on large, frequently-changing tables.
- Idempotency keys accepted on any state-changing endpoint that could plausibly be retried by a flaky mobile connection (viewing request creation, outcome reporting).

---

## 14. Testing Strategy

- **Backend:** `pytest` + `pytest-django` + `factory_boy` for model factories. Unit tests on the viewing state machine (every legal/illegal transition) and fee calculation logic are non-negotiable — these are your revenue-integrity code paths.
- **Frontend:** component tests for the glass UI kit; Playwright end-to-end tests on the critical paths only (OTP login, search → viewing request, outcome reporting) rather than chasing full coverage pre-launch.
- **Payments:** M-Pesa Daraja sandbox environment for integration tests before touching production credentials.

---

## 15. Deployment & Environments

Budget-conscious choices appropriate for a bootstrapped solo build:

| Component | Suggested host |
|---|---|
| Next.js frontend | Vercel (native fit, generous free tier) |
| Django backend | Render or Railway (simple deploys, reasonable free/low tier) |
| Postgres + PostGIS | Supabase or Railway Postgres (PostGIS extension enabled) |
| Redis | Upstash (serverless-friendly, pay-per-use) |
| Object storage | Cloudflare R2 |
| Background jobs | Celery worker + beat on the same host as the backend initially; split out only once load requires it |

Three environments: `dev` (local), `staging` (Daraja sandbox, test data), `prod`. Never point staging at real M-Pesa credentials.

---

## 16. Monitoring & Logging

- Sentry (or similar) for error tracking on both frontend and backend — free tier is enough at MVP scale.
- Structured JSON logging from Django, especially around payment callbacks and outcome-reporting transitions, since those are the events you'll need to debug fastest when something's disputed.
- Simple uptime monitoring (UptimeRobot or Better Uptime free tier) on the public site and the M-Pesa callback endpoint specifically.

---

## 17. Environment Variables (Reference)

```
# Backend
DATABASE_URL=
REDIS_URL=
DJANGO_SECRET_KEY=
JWT_SIGNING_KEY=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
AFRICASTALKING_API_KEY=
AFRICASTALKING_USERNAME=
MPESA_CONSUMER_KEY=
MPESA_CONSUMER_SECRET=
MPESA_SHORTCODE=
MPESA_PASSKEY=
SENTRY_DSN=

# Frontend
NEXT_PUBLIC_API_BASE_URL=
NEXT_PUBLIC_SENTRY_DSN=
```

Never committed — `.env` files gitignored, real values in each host's secret manager.

---

## 18. Build Roadmap

1. **Scaffold the repo** — Django + Next.js skeletons, Postgres + PostGIS running, env config.
2. **Auth & identity** — User model, OTP flow, JWT, role assignment.
3. **Listings data model** — Property/Unit (unit-level), photo upload to R2, amenities.
4. **Public search & SEO** — radius search API, glass search UI, SSR unit pages, sitemap/schema.org.
5. **Viewing lifecycle** — full state machine, approvals, reminders, outcome reporting.
6. **Referrals & fees** — attribution on matched "Rented" outcomes, M-Pesa STK push, payment states.
7. **Trust & admin** — verification workflow, reliability scoring, dispute queue, customized Django admin.
8. **Harden & launch** — Redis caching, throttling, Cloudflare rules, index tuning, freshness-decay job, soft launch in one estate cluster.

---

## 19. Pre-Launch Checklist

- [ ] Legal/tax review of the referral-fee model completed (Section AB, strategy doc)
- [ ] Data Protection Act compliance reviewed for ID/phone storage
- [ ] M-Pesa production credentials tested end-to-end in staging first
- [ ] Sitemap submitted to Google Search Console
- [ ] Dispute policy published in plain language on the public site
- [ ] First 20–30 landlord relationships secured in the launch estate cluster
- [ ] Rate limiting and OTP throttling verified under simulated abuse
- [ ] Backup/restore tested on the production database at least once before go-live
