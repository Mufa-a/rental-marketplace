# Kenyan Rental Marketplace — Strategy & Product Architecture Review

*Prepared as a critical business analysis, not a validation exercise. Where your assumptions look weak, I've said so directly.*

> **Product update — 24 September 2026:** current fees are KSh 1,500 below KSh 15,000 rent, KSh 2,500 for KSh 15,000–29,999, KSh 4,000 for KSh 30,000–60,000, and KSh 6,000 above KSh 60,000. The landlord’s rental report alone takes the unit off search and triggers an M-Pesa STK Push to their registered phone. A separate Next.js admin dashboard tracks marketplace activity, fees, and payments. Tenant browse remains free; viewing requests use M-Pesa bundles (1 for KSh 50, 3 for KSh 100, 5 for KSh 150, or 10 for KSh 250). “Homes near me” offers opt-in radius search and approximate map pins. These decisions supersede conflicting recommendations below. See [`payment-tools-and-costs.md`](payment-tools-and-costs.md) for payment flow and operating costs.

---

## A. Executive Summary

The core idea — a verified, viewing-tracked marketplace connecting tenants and landlords, with outcome reporting instead of rent collection — is sound and under-served in Kenya. The current listing landscape (Facebook groups, Jiji, OLX, BuyRentKenya, informal caretaker/agent networks) is fragmented, stale, and low-trust. There is real room for a product that makes "is this house actually still available, and can I trust this landlord" answerable.

But your two proposed monetization paths point in different directions, and one of them — **charging tenants upfront to "unlock" house access** — collides with a specific, well-known Kenyan scam pattern (pay-a-fee-for-a-house-list/contact scams that have burned thousands of renters via SMS, Facebook, and classifieds). That's not a hypothetical risk; it's the single biggest threat to your trust positioning, and it needs to shape the model, not just the messaging.

My recommendation, in short: **landlords pay on success, tenants pay nothing to browse or request viewings in the flagship model.** Run the Coast pay-per-view idea as a bounded, geo-fenced experiment, not the default architecture. Full reasoning below.

---

## B. My Understanding of the Business

A two-sided marketplace where:
- **Tenants** search/filter/save rental units (not buildings), request viewings, and report outcomes.
- **Landlords** list properties broken into units, manage availability, approve/reject viewings, and report outcomes.
- **The platform** never touches rent, deposits, or leases — its product is *discovery + verified introduction + outcome tracking*, and its revenue must come from the value of that introduction, not from processing money that was never yours to hold.
- Trust and freshness are explicitly framed as the moat, not a nice-to-have.

That framing is correct. The open question is purely: **who pays for the introduction, and when** — and that's a marketplace-design question, not a features question. Get it wrong and you either can't acquire tenants (too much friction) or can't acquire landlords (no incentive to report honestly).

---

## C. Coast vs Nairobi Monetization — Critical Analysis

**Should tenants pay?** Generally, no — not upfront, not platform-wide. Three reasons:

1. **Scam-pattern collision.** "Pay us and we'll show you houses/give you contacts" is the exact shape of a fraud pattern Kenyan renters have been burned by repeatedly (fake agents on Facebook/OLX/SMS lists who take a fee and disappear or send you to a rented/nonexistent unit). Even if your execution is honest, a new brand asking a stranger to pay before delivering anything verifiable will trigger that pattern-match instantly, especially outside your existing social proof.
2. **Wrong side of the cold-start problem.** In a two-sided marketplace, the side with more urgency and more money should subsidize the side that's harder to acquire. Landlords lose real money every vacant month (a 20k/month unit sitting empty for 6 weeks is a real, felt cost). Tenants searching casually feel no comparable urgency — charging them adds friction exactly where you can least afford it pre-trust.
3. **It taxes browsing, not value delivered.** A tenant who pays KSh 150 for "5 houses" is paying for *access*, not for a successful outcome. If none of the 5 pan out, you've charged for failure. That's a bad first impression to build a trust brand on.

**Should landlords pay?** Yes — but on success, not for listing. Kenyan landlords are already culturally accustomed to paying an agent **one full month's rent** as commission on a successful let. A referral fee that is a fraction of that (see pricing below) is an easy "yes" compared to what they already pay caretakers/agents informally, *and* it costs them nothing if the platform never produces a tenant.

**Should pricing/model vary by market?** Yes, but not by defaulting Coast to a different *architecture*. Willingness-to-pay, average rent, and trust dynamics genuinely differ by region — that's a reason to vary **fee amounts** (referral fee tiers by local rent bands), not to run two structurally different business models where one systematically resembles a scam. Treat the Coast team's proposal as a hypothesis to test in a controlled pilot (Section 32), not as the Coast production model.

---

## D. Recommended Pricing Model

**Current model (all markets): Landlord success fee plus tenant viewing-request bundles. Browsing and listing details stay free.**

| Monthly rent band | Referral/success fee (charged only on confirmed rental) |
|---|---|
| Below KSh 15,000 | KSh 1,500 |
| KSh 15,000 – 29,999 | KSh 2,500 |
| KSh 30,000 – 60,000 | KSh 4,000 |
| Above KSh 60,000 | KSh 6,000 |

This is roughly **2–8% of one month's rent**, versus the ~100% a human agent charges. That's your landlord pitch in one sentence: *"Ten times cheaper than an agent, and you only pay when it works."*

**Tenant side stays free** for browsing, filtering, saving, and opening listing details. Tenants buy viewing credits in bundles to send viewing requests; credit rules return credits when landlords decline or a pending request is cancelled/expires.

**On the Coast KSh 50/100/150/250 packages specifically** — since you asked directly:
- Psychologically the numbers are fine (round, cheap, package-upgrade logic works: 5-for-150 beats 1-for-50 on unit price, which nudges upgrades). The *pricing ladder itself* isn't the problem.
- KSh 50 is too low to be a real revenue line once you net M-Pesa transaction costs and support overhead against it — it functions as a friction tax, not a monetizable product.
- The 10-house package is the highest abuse risk: it's cheap enough to buy in bulk and share/resell access, or to scrape landlord contacts and go direct immediately.
- Fix, if you pilot it: charge *only after* the landlord has confirmed the unit is currently available (never charge against an unconfirmed listing); unused credits expire in 60–90 days; any landlord-cancelled or "property doesn't exist" outcome **automatically and instantly restores the credit** — no manual refund process, no dispute needed, or you will bleed trust immediately.

---

## E. Tenant Economics

- Zero cost to search, save, compare, or open a listing.
- Viewing requests use the published M-Pesa bundles; browse access and listing details remain free.
- What the tenant actually "pays" in the flagship model is *attention and honesty*: a viewing request obligates them to report the outcome, and repeated no-shows/non-reporting degrades their reliability score and eventually throttles their request quota.

## F. Landlord Economics

- Free to list, free to get verified, free to receive requests.
- Pays the success fee in Section D when the landlord reports a viewing converted to a rental. The unit is unpublished immediately and an STK Push goes to the landlord’s registered phone.
- Value delivered even without a successful conversion yet: qualified, non-time-wasting leads (tenant reliability scores mean fewer flaky viewing requests than open Facebook posting), and a public reliability score that makes *their* listings more trustworthy — a competitive advantage over caretakers still posting on Facebook groups.

---

## G. Marketplace Flywheel

```
More landlords list free (low risk, high potential upside)
        ↓
More real, fresh inventory → tenants find the app actually useful
        ↓
More tenants search/request viewings (free = low friction to join)
        ↓
More viewing volume → more completed viewings → more rentals
        ↓
Landlords see real ROI → refer other landlords, pay fees willingly
        ↓
Revenue funds verification, trust features, marketing
        ↓
Trust becomes visibly higher than Facebook/Jiji/OLX
        ↓
More landlords list (loop repeats)
```

The critical insight: **because landlords pay on success, listing is a zero-risk action for them.** That's what makes the supply side easy to bootstrap — you're not asking for money or effort upfront, just a listing.

---

## H. Anti-Bypass Strategy

Be honest with the team: **nothing stops two humans from exchanging a phone number and going private if they want to.** The goal isn't prevention, it's making honest reporting the path of least resistance and bypass the path of active effort and risk.

**Mechanics:**
- Every approved viewing gets a unique ID (`VW-XXXXX`), timestamped, tied to tenant + landlord + unit.
- After the scheduled viewing time, **both parties get a mandatory outcome prompt** (push/SMS/WhatsApp): Rented / Still deciding / Did not rent (landlord) and I rented / Did not rent / Still deciding (tenant).
- Matching "Rented" answers → referral fee triggers, unit auto-marked unavailable, rental recorded.
- Non-response after reminders (e.g., 3 nudges over 7 days) → viewing marked `OUTCOME_UNKNOWN`, and the unit's listing is auto-flagged "availability needs confirmation" — which **costs the landlord visibility**, giving them a reason to respond honestly rather than ignore you.
- **Incentive, not just enforcement:** landlords who consistently report outcomes (good or bad) accumulate a visible reliability badge that increases their listing's placement; landlords who go quiet repeatedly lose visibility. That's a carrot strong enough to matter, because visibility is what gets units rented fast.
- Repeated pattern detection: if a landlord has many `COMPLETED` viewings but almost no reported `RENTED` outcomes relative to market norms, flag for manual review — a real (if imperfect) bypass signal.
- Time-limited attribution window (Section N) closes the "we waited three months and then transacted" loophole partially, though not completely — say this plainly to the team, don't oversell it.

---

## I. Trust & Verification Strategy

Three-tier realism, not "100% scam-free" claims:

| Level | What's checked | Badge |
|---|---|---|
| Basic | Phone number verified (OTP), email verified | "Registered" |
| Standard | National ID matched to name, at least one property with photos matching a geotagged location | "ID Verified" |
| Trusted | Standard + a completed, mutually-confirmed rental history on the platform, or a manual site visit for high-value listings | "Trusted Landlord" |

Additional trust surface:
- **Freshness label** on every listing (Section on freshness below) — this alone differentiates you from every stale Facebook post.
- **Report Listing** button on every unit, feeding a lightweight moderation queue.
- **Duplicate detection**: same phone/ID + same GPS coordinates + similar photos (perceptual hash) flags likely duplicate postings for review, rather than auto-blocking (avoid punishing legitimate agents managing multiple units in one building).
- Tenant reliability score, visible to landlords when they review a request (protects landlords' time, which is core to their buy-in).

---

## J. Complete Tenant Journey

1. Land on site/app — browse and search **without an account** (account required only to save, request a viewing, or message).
2. Search by city/estate/landmark/map + radius, with budget, bedrooms, amenities, move-in date.
3. Filter results; see verification badge + freshness label on each card.
4. Open a unit page (not a building page) — photos, video, amenities, rent, availability status, landlord reliability.
5. Save/compare units.
6. Register (lightweight: phone OTP) at the point of requesting a viewing — this is the natural, motivated moment to ask for an account.
7. Request viewing → pick a time slot the landlord has marked available.
8. Get landlord approve/reject/reschedule notification.
9. Attend viewing.
10. Report outcome (Rented / Did not rent / Still deciding).
11. If rented — done, unit marked unavailable, nothing further owed by the tenant. If not — continue searching, request history retained for context.

## K. Complete Landlord Journey

1. Register (phone/email).
2. Submit ID + property ownership/management proof for verification.
3. Create property → add units individually (unit-level rent, bedrooms, bathrooms, amenities, photos, availability).
4. Set viewing availability windows.
5. Receive viewing requests; approve/reject/reschedule with one tap.
6. Host the viewing.
7. Report outcome.
8. On confirmed rental: unit auto-marked unavailable, referral fee invoiced (M-Pesa STK push), receipt issued.
9. Reconfirm availability periodically to keep freshness/visibility high on unrented units.
10. View a simple performance dashboard: views, requests, viewings held, conversion rate, comparison to similar units in the area (a genuinely valuable, differentiated feature).

**Why a landlord bothers:** free distribution beyond their existing network, pre-filtered leads (reliability-scored tenants instead of randoms from a Facebook comment thread), and a fee structure that's a fraction of what an agent costs and only due on success.

## L. Complete Admin Journey

- **Verification queue**: review landlord ID + property submissions, approve/reject/request more info.
- **Listings**: search/filter, force-unpublish, merge suspected duplicates.
- **Viewings**: full audit trail per viewing ID, outcome status, time since last confirmation.
- **Disputes**: queue of conflicting tenant/landlord outcome reports, with the shared evidence (viewing timestamp, messages, prior history of each party) surfaced side by side; admin issues a ruling (Rented/Not rented/Unresolved) which finalizes fee liability.
- **Fraud/suspicious activity**: flagged accounts (duplicate GPS+photos, abnormal cancellation rates, payment abuse patterns), with one-click restrict/suspend.
- **Payments**: fee invoices, payment status (Pending/Successful/Failed/Refunded/Disputed), refund issuance.
- **Analytics**: the metrics in Section 30, on one dashboard.
- **Audit log**: every state change, who/when, immutable.

**Dispute workflow specifically:** conflicting outcome → auto-opened dispute case → both parties get 48h to submit their side (free text + optional evidence) → admin reviews viewing metadata (was it actually approved/scheduled, message history, prior reliability of both parties) → ruling issued → fee liability and reliability scores updated accordingly. Publish a clear, simple public-facing dispute policy so both sides know the rules going in.

---

## M. Viewing State Machine

```
REQUESTED
  → PENDING_LANDLORD
      → APPROVED → SCHEDULED → COMPLETED → OUTCOME_PENDING
                                                  → RENTED
                                                  → DID_NOT_RENT
                                                  → STILL_DECIDING → (re-enters OUTCOME_PENDING after follow-up window, or auto-closes)
                                                  → DISPUTED (conflicting reports) → resolved by admin ruling
      → REJECTED (landlord declines)
      → RESCHEDULED → back to SCHEDULED
  → EXPIRED (landlord doesn't respond within X days)
  → CANCELLED (either party, before the appointment)
  → NO_SHOW (tenant or landlord didn't attend — captured at outcome step, distinct from DID_NOT_RENT)
```

**Key transition rules:**
- `EXPIRED` after 48–72h of landlord silence — protects tenant experience, and dings landlord responsiveness score.
- `NO_SHOW` is tracked separately from a completed-but-unsuccessful viewing, because repeated tenant no-shows should throttle their request quota, while repeated landlord no-shows should hurt their reliability badge.
- A `DISPUTED` viewing never auto-resolves — it requires an admin ruling to close, so fee liability is never ambiguous.

---

## N. Referral Attribution System

Each successful viewing generates a referral record: tenant, landlord, property, unit, viewing ID, timestamp, attribution status, outcome, evidence trail (messages + confirmations).

**Attribution window: 60 days from the viewing date.** Reasoning: 30 days is too tight for the realistic Kenyan rental decision cycle (many tenants view several units before committing, especially relocators); 90 days is long enough that legitimate independent transactions (tenant finds a *different* unit through the same landlord, unrelated to your introduction) start getting wrongly attributed to you, which damages landlord trust in the fee logic. 60 days balances both.

If a landlord reports "rented" for the *same unit* within the attribution window of a viewing you facilitated, the fee is presumed due unless they can show it was a different, unrelated tenant (evidence-based override in the dispute flow, not an automatic charge with no recourse).

---

## O. Fraud/Abuse Scenarios & Defenses

| Actor | Abuse | Defense |
|---|---|---|
| Tenant | Fake/duplicate accounts | Phone OTP + device fingerprinting; cap active requests per verified phone |
| Tenant | Repeated no-shows | Reliability score drop → throttled request quota after N no-shows |
| Tenant | Payment/chargeback abuse (if any paid tier exists) | M-Pesa is push-confirm, not card-chargeback-prone; still cap refund frequency per account |
| Tenant | Harassing landlords | Report button + rate limiting + suspension on repeated reports |
| Landlord | Fake/nonexistent property | Verification tier + tenant "property doesn't exist" report auto-escalates to suspension review |
| Landlord | Duplicate listings | GPS + photo hash matching, manual merge queue |
| Landlord | Marks unit unavailable to dodge fee, relists later | Track unit history; relisting the *same unit* within the attribution window re-triggers attribution check |
| Landlord | False "did not rent" to avoid fee | Tenant's conflicting "I rented" report opens a dispute; pattern of tenant-contradicted "did not rent" outcomes flags the landlord account |
| Landlord | Multiple shadow accounts | ID verification tied to phone/ID number, not just email |

---

## P. Refund/Dispute Strategy

- Any confirmed landlord-side failure (property doesn't exist, cancelled with no reschedule, materially misrepresented) → **instant, automatic refund/credit restoration**, no ticket required.
- Genuine disagreement about outcome (rented vs not) → formal dispute flow (Section L), admin-ruled, 48–72h SLA target.
- Fee disputes (landlord disputes that a rental was platform-attributable) → same flow, resolved against the evidence trail (Section N).
- Publish refund/dispute policy in plain language on the public site before launch — this is a trust surface, not just an ops process.

---

## Q. MVP Feature List — What Must Be In, What Waits, What's Cut

**Must be in MVP:**
- Tenant: search/filter/location search, unit detail pages, save, viewing request, viewing history + outcome reporting, basic notifications.
- Landlord: registration + basic verification (phone/ID), property + **unit-level** management, photos, availability toggle, viewing request handling, outcome reporting, simple dashboard.
- Admin: user/listing management, verification queue, viewing/outcome audit trail, basic dispute handling, suspicious-activity flags, payment status view.
- Payments: M-Pesa STK push for landlord referral fee only. No tenant payments in MVP — this removes an entire category of scam-perception risk and refund complexity from day one.

**Should wait (v1.1/v2):**
- Smart matching/scoring beyond simple filters.
- Landlord analytics beyond basic conversion numbers.
- In-app messaging (start with revealing verified contact info post-approval; full chat adds real moderation overhead).
- Premium placement / boosted listings.
- Multi-language/SMS-first flows for lower-smartphone-penetration segments.

**Should not be built at all (for now):** rent collection, lease management, accounting, AI-heavy matching, blockchain/crypto, complex subscription tiers, tenant credit scoring. All correctly excluded in your own brief — I agree with every exclusion you listed.

---

## R. Future Roadmap

| Horizon | Opportunities |
|---|---|
| NOW (MVP+) | Verified badges, freshness system, unit-level listings, outcome-based fee |
| NEXT (v1.1–v2) | Landlord analytics/vacancy insights, in-app messaging, premium placement, professional-photo add-on service, relocation mode polish |
| LATER | Verified agent/property-manager accounts, virtual viewings, moving/utility-connection partnerships, neighborhood intelligence, rental price trend data, corporate/student housing verticals, property-management SaaS upsell to your best landlords |

---

## S. Database / Entity Architecture

Your list is close; key changes: split `Viewing` into `ViewingRequest` (the ask) and `Viewing` (the scheduled/held event) since they have different state machines; merge `ViewingOutcome` + `RentalOutcome` into one `Outcome` record per side (tenant outcome, landlord outcome) to make the dispute-matching logic simple; add `ReliabilityScore` as a derived/cached entity, not a raw table you hand-edit.

```
User ──< TenantProfile / LandlordProfile
LandlordProfile ──< Property ──< Unit ──< PropertyMedia
Unit ──< Amenity (M2M)
TenantProfile ──< SavedProperty, SearchPreference
TenantProfile ──< ViewingRequest >── Unit
ViewingRequest ──1:1── Viewing (once approved+scheduled)
Viewing ──< Outcome (one per party: tenant_outcome, landlord_outcome)
Viewing ──1:1── ReferralAttribution ──< ReferralFee ──< Payment
Verification (polymorphic: Landlord or Property or Unit)
Report, Dispute (references Viewing/Listing + involved Users)
Notification (polymorphic target)
AuditLog (append-only, references any entity)
AccountRestriction ──> User
```

Relationships: a `Property` has many `Unit`s (the property≠unit fix you asked for); a `Unit`'s availability is independent of its siblings; a `ViewingRequest` always resolves into either a terminal negative state or a `Viewing`, and a `Viewing` always resolves into matched/mismatched `Outcome`s, which is what drives `ReferralAttribution` → `ReferralFee` → `Payment`.

---

## T. Role / Permission Matrix

| Action | Tenant | Landlord | Admin |
|---|---|---|---|
| Browse/search | ✅ (no account) | ✅ | ✅ |
| Request viewing | ✅ (account) | — | ✅ |
| Approve/reject viewing | — | ✅ (own units) | ✅ (any) |
| Create/edit unit | — | ✅ (own) | ✅ (any) |
| Report outcome | ✅ (own viewings) | ✅ (own units) | ✅ |
| Verify landlord/property | — | — | ✅ |
| Issue refund | — | — | ✅ |
| Resolve dispute | — | — | ✅ |
| View audit log | — | — | ✅ |
| Suspend account | — | — | ✅ |

---

## U. Technical Architecture

- **Frontend:** Next.js (React) — SSR helps SEO for public listing pages, which matters for organic tenant discovery.
- **Backend:** Django + DRF — your instinct is right; fast to build verification/admin-heavy workflows, strong ORM for the relational model above, mature ecosystem for RBAC and audit logging.
- **Database:** PostgreSQL, with PostGIS extension for radius/geo search (city/estate/landmark + radius queries need real geo indexing, not naive lat/long math).
- **Storage:** S3-compatible object storage for photos/video, with a CDN in front for image delivery speed.
- **Auth:** JWT or session-based (DRF + SimpleJWT), phone OTP as the primary tenant/landlord identity anchor (more reliable than email in this market).
- **Notifications:** SMS (Africa's Talking or similar) for critical actions (viewing approved, outcome reminder), push for app users, email as backup — SMS-first is not optional in this market.
- **Payments:** M-Pesa Daraja API (STK push) for the landlord referral fee; design the payment state machine (Pending/Successful/Failed/Refunded/Disputed) as its own service boundary so it's easy to add card/other rails later without touching core marketplace logic.
- **Maps:** Google Maps or Mapbox — Mapbox is materially cheaper at scale if usage grows, worth prototyping on Google first for developer speed then reassessing before scale costs bite.

Priorities in order for a startup: security and correctness of the fee/outcome logic (this is literally your revenue integrity) > maintainability > low cost > developer experience > premature scalability. Don't over-engineer for scale you don't have yet.

---

## V. Unit Economics — Realistic Kenyan Scenarios

**Primary model (landlord success fee):**

Assume 10,000 viewing requests in a month, avg referral fee KSh 3,000 (illustrative blended amount across the current rent bands):

| Stage | Volume | Note |
|---|---|---|
| Viewing requests | 10,000 | — |
| Completed viewings (30%) | 3,000 | per your own funnel assumption |
| Successful rentals (10% of requests) | 1,000 | ~33% of completed viewings convert — plausible |
| Bypassed/unreported (20% of successful) | 200 | lost fee |
| Fee-eligible rentals | 800 | |
| **Gross monthly revenue** | **KSh 800,000** | 800 × 1,000 |
| Less disputes/refund leakage (~8%) | −KSh 64,000 | conservative |
| **Net monthly revenue (illustrative)** | **~KSh 736,000** | at this volume |

Scale sensitivity: at 1,000 requests/month (early days) → net revenue roughly **KSh 73,600**; at 50,000 requests/month (mature, multi-city) → roughly **KSh 3.68M**. Revenue scales with *viewing request volume*, not raw tenant signups — which is why your growth metric should be requests, not registrations.

**For comparison — the Coast tenant-fee model, at face value (why I don't recommend it as primary):**

| Tenants paying avg KSh150 package | Gross revenue | Realistic net after ~15% refund/dispute drag + Mpesa fees |
|---|---|---|
| 1,000 | KSh 150,000 | ~KSh 125,000 |
| 10,000 | KSh 1,500,000 | ~KSh 1,250,000 |
| 50,000 | KSh 7,500,000 | ~KSh 6,250,000 |

These numbers look competitive on paper, but they assume you can *acquire* tens of thousands of tenants willing to pay upfront with zero track record — which is the actual bottleneck, not the math. The landlord-fee model's numbers look smaller per-unit but are far more achievable because landlords face a real cost of vacancy and a genuinely lower-risk ask (pay only if it works).

---

## W. First 100 Landlords Strategy

Generic "use social media" is banned, so specifics:
1. **Target existing caretakers/agents managing multiple units**, not individual homeowners first — one relationship can onboard 5–20 units at once (this matches your unit-level data model perfectly).
2. **Walk specific buildings.** Pick 3–5 estates with known apartment density (e.g. Kilimani, Kileleshwa, Ruaka, South B in Nairobi; Nyali, Bamburi in Mombasa) and physically visit caretakers/watchmen — they know who manages vacant units and are often the actual point of contact, not the owner.
3. **Free onboarding session, in person, first 20 landlords** — take the photos and enter listings for them if needed; remove all effort barriers for the earliest adopters.
4. **Undercut agent commission explicitly in the pitch**: "You already pay a month's rent to an agent when it works. We charge a fraction, and only when it works." This is a concrete, comparable number landlords already understand.
5. **Seed with your own network first** (Erick — if you or people you know manage or own any rental units in Nairobi, that's your literal first 1–5 listings, free of cold-start risk).
6. **Target property Facebook groups directly** — not to advertise, but to identify active posters (they're already trying to solve the exact problem you solve) and DM them personally with a specific pitch, not a broadcast post.

## X. First 1,000 Tenants Strategy

1. **SEO on unit-level pages, not building-level** — "1 bedroom Westlands KSh 25,000" style long-tail pages index far better than generic listing pages, and this is free distribution that compounds.
2. **Piggyback the relocation use case explicitly** — target university WhatsApp/Facebook groups and corporate relocation channels (new grads, upcountry-to-Nairobi movers) with your radius/relocation-mode search as the specific hook, since existing tools handle this badly.
3. **Because tenant access is free, the ask is trivially low-friction** — your acquisition content can be "search now, no account needed" rather than "sign up for our platform," which converts far better cold.
4. **Referral loop**: a tenant who successfully finds a place is your best distribution — a simple "helped me find my house" share prompt at the moment of a confirmed rental (peak satisfaction moment).
5. **Estate agents/caretakers you onboard as landlords will organically drive tenant traffic to their own listings** — this is the flywheel doing double duty; don't underinvest in landlord onboarding thinking it's separate from tenant growth.

---

## Y. Key Risks & Mitigation

| Risk | Why it matters | Probability | Impact | Mitigation |
|---|---|---|---|---|
| Tenant-pay model reads as a scam | Kenya has real, recent scam history matching this exact pattern | High (if you charge tenants upfront) | Severe (kills trust brand permanently) | Don't make it the default model; if piloted, radical transparency + instant refunds + small geo-fenced test only |
| Landlords resist referral fees | Feels like "another agent tax" if not framed well | Medium | High | Explicit cheaper-than-agent framing, fee only on success, transparent tiers |
| Bypass to avoid fees | Rational economic behavior for both sides | High (some baseline is inevitable) | Medium (accepted cost of doing business) | Reliability incentives, not pure enforcement (Section H); design for reduction, not elimination |
| Fake/stale listings erode trust | This is the core problem you're solving — failure here is existential | Medium-High | Severe | Verification tiers, freshness decay, report button, duplicate detection |
| Chicken-and-egg (no landlords → no tenants → no landlords) | Classic marketplace failure mode | High at launch | Severe if unaddressed | Zero-risk-to-list landlord model + manual concierge onboarding of first 100 (Section W) |
| Getting density in one geography | Sparse inventory across many cities is worse than deep inventory in one | Medium | High | Launch single-city, single-cluster-of-estates first; resist expanding until density KPIs are met |
| Agents/informal brokers dominate anyway | They have existing trust and relationships | Medium | Medium | Recruit them *as* your landlord-side power users rather than competing with them |
| Payment/M-Pesa fee friction on small transactions | Eats margin on low-value transactions | Medium | Low-Medium | Avoid small tenant micro-payments; landlord fees are large enough to absorb Daraja costs comfortably |
| Dispute volume overwhelms a small team | Manual review doesn't scale linearly | Medium | Medium | Clear, narrow dispute criteria; automate the obvious cases (landlord-confirmed cancellations) |

---

## Z. Final Business Model Recommendation

If this were my money:

1. **Who pays:** Landlords, on success. Tenants: free.
2. **How much:** Tiered flat referral fee, KSh 1,500–6,000 by rent band (Section D).
3. **When:** When the landlord reports a successful rental via the outcome flow; the home is unpublished and the STK push begins immediately.
4. **What exactly they're paying for:** A verified, tracked introduction that resulted in a filled vacancy — priced far below the agent-commission norm they already accept.
5. **What's free:** Everything for tenants; listing, verification, and viewing management for landlords.
6. **Coast:** Do not deploy the pay-per-view model platform-wide. Run it as a bounded pilot in a handful of Coast estates, opt-in, clearly labeled as a trial, with instant-refund guarantees, and compare its economics and complaint rate against the landlord-fee control group before deciding anything permanent.
7. **Nairobi:** Landlord success-fee model, full stop, from day one.
8. **Should pricing differ by market:** Yes — by adjusting the fee tiers to local rent bands, not by changing who pays.
9. **Bypass prevention:** Incentive-based reliability scoring + mandatory outcome prompts (Section H) — realistic reduction, not elimination.
10. **Refunds:** Instant/automatic for landlord-side failures; no tenant refunds needed in the flagship model since tenants never pay upfront.
11. **Disputes:** Admin-ruled within 48–72h against the evidence trail (Section N/P).
12. **Verification:** Tiered (Basic/Standard/Trusted), realistic language, never "100% safe" claims.
13. **First landlords:** Manual, in-person, caretaker/agent-first (Section W).
14. **First tenants:** Free-access SEO + relocation-use-case targeting (Section X).
15. **MVP:** Section Q, with **no tenant payments at all in v1**.
16. **What not to build:** Everything you already correctly excluded, plus: don't build tenant payments until you have data suggesting a specific premium (not access-gate) use case for it.
17. **Strongest defensible advantage:** The outcome-tracking/freshness system — competitors can copy verification badges, but the mandatory-outcome-reporting data asset compounds over time and is genuinely hard to replicate without your fee-alignment structure.
18. **What could kill this:** Launching the tenant pay-gate as the default model and getting tagged as a scam-adjacent app before trust is established — recoverable in theory, very costly in practice in a market this word-of-mouth-driven.

---

## AA. What I Would Change About the Original Idea

- **Drop tenant-pay-to-view as the flagship model.** This is the single biggest change — it inverts the marketplace-design logic and creates unnecessary brand risk in a market with scam-pattern baggage.
- **Don't treat Coast vs Nairobi as "two business models."** Treat it as one model with region-tunable fee amounts, plus one explicitly-labeled pricing experiment.
- **Unit-level modeling from day one** — you already got this right; just flagging it as correct and non-negotiable, don't let MVP pressure collapse it back to building-level listings.
- **No tenant payments anywhere in MVP**, not even the Coast experiment, until v1 — validate the core loop first, introduce the pricing experiment as a controlled test once you have baseline trust metrics to compare against.
- **In-app chat waits.** Contact-reveal post-approval is enough for MVP and avoids a moderation burden you don't need yet.

## AB. 10 Most Important Open Questions Before Development

1. Which single city/estate cluster will you launch in first, and do you already have a path to your first 20–30 real landlord relationships there?
2. What exact fee tiers and rent-band boundaries will you commit to for the landlord success fee — do you have real rent data for your launch area to set these accurately?
3. Who verifies landlord ID/property ownership in practice — manual admin review by your own team, or a third-party KYC service, and what's the target turnaround time?
4. What's your actual legal position on collecting a "referral/success fee" — does this require any licensing or registration as a real-estate-adjacent service in Kenya? (Needs professional Kenyan legal review — don't guess here.)
5. What tax treatment applies to referral fee revenue, and do you need to issue receipts/invoices in a specific format for landlords?
6. What's your data protection posture for storing tenant/landlord ID numbers and phone numbers — are you compliant with Kenya's Data Protection Act requirements for this kind of personal data?
7. Who staffs dispute resolution at launch, and what's the realistic team capacity for a 48–72h SLA at your expected volume?
8. What's the minimum viable verification bar you'll actually enforce before a landlord's first listing goes live — will you launch with unverified listings visible (labeled) or block visibility until verified?
9. What M-Pesa integration path will you use (Daraja direct vs. a payment aggregator), and what are the realistic settlement/reconciliation timelines for landlord fee payouts... actually, since you're only *collecting* fees, not paying out — confirm there's no payout leg needed at all in v1?
10. If the Coast pilot underperforms or overperforms the landlord-fee control significantly, what specific metric threshold decides whether you scale it, kill it, or blend elements of both?

---

*This document intentionally stops short of code, models, or endpoints per your instruction. Happy to move into Django models, DRF API design, or the Next.js information architecture once the model above is reviewed and adjusted.*
