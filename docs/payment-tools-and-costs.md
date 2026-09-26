# Nyumbani: payment tools and operating costs

**Prepared:** 23 September 2026  
**Currency:** Kenya shillings (KSh), with USD estimates converted at CBK indicative rate **KSh 129.46 per US$1** on 22 September 2026. Bank/card exchange rates and tax treatment can differ.  
**Purpose:** a plain-language guide for explaining how payments work, what the software uses, and what the business should budget for.

> Prices below are public list prices or planning estimates, not supplier quotations. Get written quotes before committing to a payment tariff, sender ID, hosting contract, or tax treatment. Provider prices can change.

## Short version

- Tenants can browse homes for free. Sending viewing requests uses a paid credit from one of four M-Pesa bundles; the marketplace still does not collect rent or deposits.
- A landlord success fee is created when the landlord reports that a viewing converted to a rental. The listing is unpublished immediately and an M-Pesa STK Push is sent to the landlord’s registered phone. The payment integration is coded, but it is not live until Safaricom credentials, a merchant account, and a public HTTPS callback are configured.
- The planned commercial stack with an interactive nearby map costs about **US$124.60/month (about KSh 16,131/month)** before SMS, M-Pesa merchant charges, tax, support, and any usage overages. This is an illustrative budget, not a vendor quote or an already-running deployment.
- SMS and payment fees vary with actual use and provider contracts. R2 photo storage should be free at small scale within Cloudflare's included tier.
- Domain, sender ID, and merchant onboarding are launch/setup costs. The SMS sender ID costs listed below are from the provider's 2025 Kenya price sheet and should be reconfirmed.

## 1. What the app charges and who pays

The landlord pays a one-time success fee when they report a successful rental. Fees rise with rent, beginning at KSh 1,500; these are gross marketplace charges before operating costs.

| Monthly rent | Landlord success fee |
|---:|---:|
| Below KSh 15,000 | KSh 1,500 |
| KSh 15,000–29,999 | KSh 2,500 |
| KSh 30,000–60,000 | KSh 4,000 |
| Above KSh 60,000 | KSh 6,000 |

The team’s updated proposal adds **tenant viewing bundles**, purchased before sending viewing requests:

| Bundle | Price | Effective price per request |
|---:|---:|---:|
| 1 viewing request | KSh 50 | KSh 50 |
| 3 viewing requests | KSh 100 | About KSh 33 |
| 5 viewing requests | KSh 150 | KSh 30 |
| 10 viewing requests | KSh 250 | KSh 25 |

Browsing, searching, and opening listing pages stay free. One credit is reserved when a tenant sends a request and is consumed after the landlord approves. The proposed fairness rule returns the credit if the landlord declines, the tenant cancels before approval, or the request expires unanswered. The app does not collect rent or deposits. The tenant bundle schedule is a new product change and supersedes the older tenant-free MVP statements in the strategy document.

The landlord fee schedule above is the current code behavior. The landlord report alone creates the fee, removes the unit from search, and initiates an STK Push to the verified account phone. If Daraja is unavailable or unconfigured, the fee remains due and can be retried from the landlord dashboard.

These are **gross marketplace fees**, not profit. Payment processing, SMS, hosting, taxes, support, refunds, and failed-payment handling reduce what the business keeps. Do not describe the fee as profit or promise a net margin until those costs and taxes are accounted for.

## 2. Payment flow: M-Pesa Daraja

### What happens in the current product

1. When a landlord reports a successful rental, the backend creates a landlord success-fee record and unpublishes the unit.
2. The backend immediately asks Safaricom Daraja to send an STK Push to the landlord’s registered phone number.
3. The landlord approves or cancels the prompt on their handset.
4. Safaricom calls the app’s HTTPS callback with the result. The app records it and marks the landlord fee paid. If STK initiation fails or Daraja is not configured, the fee remains due and can be retried from the landlord dashboard.

Tenants also purchase a viewing bundle using an M-Pesa STK Push. Safaricom confirmation adds credits to the tenant account. Each request reserves one credit; approval consumes it. A decline, tenant cancellation before approval, or seven-day unanswered-request expiry restores it. The tenant never pays per listing-page view.

The project uses Daraja integration code and the `CustomerPayBillOnline` STK Push transaction type. This is a **PayBill-style merchant collection setup**. It is not a Buy Goods till integration, and the two can have different tariffs. The code does not currently distribute a payment to a landlord or automatically split a fee between parties: the fee is collected by the merchant account configured for the app.

### What must be obtained/configured before taking live money

- Safaricom Daraja production app credentials and the approved merchant shortcode / PayBill configuration.
- A public HTTPS callback URL, a strong callback token, and monitoring/reconciliation for transactions that time out or arrive late.
- A written Safaricom tariff for this specific PayBill and transaction type, plus any account setup, settlement, reversal, or minimum charges.
- Clear customer-facing fee terms, receipts, support and refund/dispute handling.

The [Daraja developer portal](https://developer.safaricom.co.ke/) provides API access information, but the portal alone does not establish that this merchant account has zero fees. Safaricom's [PayBill FAQ](https://www.safaricom.co.ke/media-center-landing/frequently-asked-questions/m-pesa-paybill?tmpl=component) points to the relevant business tariff. The publicly posted [M-Pesa Business Till tariff](https://www.safaricom.co.ke/images/Downloads/the-m-pesa-business-till-tariff.pdf) describes a Buy Goods/Till tariff; its often-quoted 0.5% charge capped at KSh 200 must **not** be assumed to apply to this PayBill setup.

### M-Pesa cost planning

Safaricom's actual merchant charge is **not confirmed for this project**. Request the PayBill tariff in writing. To illustrate how a percentage fee would affect revenue only, at a hypothetical 0.5% merchant rate the charge would be:

| Fee collected | Example at 0.5% | Amount before other costs |
|---:|---:|---:|
| KSh 1,500 | KSh 7.50 | KSh 1,492.50 |
| KSh 2,500 | KSh 12.50 | KSh 2,487.50 |
| KSh 4,000 | KSh 20 | KSh 3,980 |
| KSh 6,000 | KSh 30 | KSh 5,970 |

These are **scenario calculations, not Safaricom's quote**. They do not include SMS, hosting, tax, or any fixed/settlement charges. Confirm whether the merchant fee is deducted from the marketplace, charged to the payer, or handled another way under the signed agreement.

## 3. Tools used by the app and their costs

| Tool/service | What it does | Cost treatment |
|---|---|---|
| Safaricom Daraja / M-Pesa | STK Push collection of landlord success fees | No project-specific merchant tariff is confirmed. Budget using the written PayBill contract, not an assumed Buy Goods rate. |
| Africa's Talking SMS | OTPs and viewing/payment status notifications | Per SMS and possibly sender-ID setup. Use the current quote; see estimates below. |
| Cloudflare R2 | Listing photographs | Free monthly allowance covers 10 GB-month storage, 1 million Class A operations, 10 million Class B operations; R2 Standard has no egress charge. Beyond allowance, Standard list prices are $0.015/GB-month, $4.50/million Class A and $0.36/million Class B. |
| PostgreSQL with PostGIS | Listings, accounts, viewings, fee records, and location radius search | Local Docker development is free as a vendor service; a production managed database is a monthly cost. |
| Redis / Redis-compatible cache | Short-lived search cache and application support | Local Docker is free; managed production memory is usage-priced. |
| Render | Illustrative host for Django API, database and cache | Monthly service/database/workspace charges; see commercial estimate below. Not yet a confirmed deployment/provider selection. |
| Vercel | Illustrative host for the Next.js website | Commercial project budget uses Pro at $20/month. Hobby is intended for personal/non-commercial use. Not yet a confirmed deployment/provider selection. |
| Domain name | Public website address, e.g. a `.co.ke` domain | Annual renewal. Example public `.co.ke` price listed by Safaricom Domains is KSh 1,160/year; compare registrars and renew on time. |
| Nearby map tiles | Interactive map for “Homes near me” pins | PostGIS and browser geolocation do not have a per-search vendor fee. The recommended commercial tile plan is MapTiler Flex at $25/month, including 25,000 map sessions; extra sessions/search requests are usage-priced. The app has an OpenStreetMap fallback for development, but OSM's public tile servers are best-effort and may withdraw access, so do not make them the dependable production map service. |
| Geocoding | Turns a typed address into coordinates | Not included. New listings require a property pin/coordinates; the landlord can use device location while physically at the home or enter coordinates manually. |
| Email / WhatsApp provider | Email or WhatsApp messaging | Not currently integrated or included in this budget. |
| Error monitoring (e.g. Sentry) | Captures application errors | No live Sentry integration is included in this cost estimate; add only after selecting and configuring it. |

R2 prices and allowances are from [Cloudflare's R2 pricing page](https://developers.cloudflare.com/r2/pricing/). Hosting prices are from [Render's pricing page](https://render.com/pricing) and [Vercel's pricing page](https://vercel.com/pricing); Vercel explains its [Hobby plan limitations](https://vercel.com/docs/plans/hobby). Domain example: [Safaricom Domains pricing](https://domains.safaricom.co.ke/index.php?rp=%2Fdomain%2Fpricing). Map budget uses [MapTiler's pricing](https://www.maptiler.com/cloud/pricing/); see [OpenStreetMap tile terms](https://operations.osmfoundation.org/policies/tiles/) for the development fallback's limits.

### SMS rate and sender ID planning

The Africa's Talking Kenya 2025 bulk-SMS sheet listed a basic band of **KSh 0.80 per SMS, before 16% VAT** across Safaricom and other Kenyan networks. If 16% VAT applies to the invoice, this is KSh 0.928 (about **KSh 0.93**) per SMS. At that rate:

| Successful SMS deliveries | Approx. spend including 16% VAT |
|---:|---:|
| 100 | KSh 93 |
| 1,000 | KSh 928 |
| 10,000 | KSh 9,280 |

These calculations assume one SMS segment per message. Long messages can split into multiple billable segments; failed delivery/retry behavior and current rate bands can change the bill. A 1,000-message monthly allowance should therefore be planned at about **KSh 1,000 plus any sender-ID and account costs**, rather than treated as an exact cap.

The same 2025 provider sheet listed setup examples for a transactional sender ID: Safaricom + Airtel bundle KSh 14,100; Safaricom only KSh 8,700; Airtel only KSh 8,700; Telkom KSh 4,500; Equitel KSh 9,000. These are historical public prices, and the sheet did not clearly establish whether setup fees include VAT. Confirm current price, approval requirements, sender-ID availability, and tax with Africa's Talking before budgeting. Transactional IDs are for service messages such as OTPs, not promotional campaigns. Start with the provider's current [Kenya Bulk SMS pricing help page](https://help.africastalking.com/en/articles/12381163-bulk-sms-kenya).

## 4. Illustrative monthly commercial-launch budget

This estimate is one possible paid setup for a small commercial launch using Vercel for Next.js and Render for Django, PostgreSQL/PostGIS, and Redis-compatible Key Value. It is **not** a production quote and does not imply these accounts have been purchased.

| Line item | Planning price (USD/month) | Approx. KSh/month |
|---|---:|---:|
| Render Pro workspace (team/commercial production budget assumption) | $25.00 | KSh 3,237 |
| Django API service, 1 CPU / 2 GB example tier | $25.00 | KSh 3,237 |
| Managed PostgreSQL, 1 GB example tier | $19.00 | KSh 2,460 |
| PostgreSQL storage, assume 2 GB at $0.30/GB | $0.60 | KSh 78 |
| Redis-compatible Key Value, 256 MB example tier | $10.00 | KSh 1,295 |
| Vercel Pro website plan | $20.00 | KSh 2,589 |
| MapTiler Flex commercial map plan | $25.00 | KSh 3,237 |
| **Estimated recurring subtotal** | **$124.60** | **about KSh 16,131** |

Conversion uses CBK's indicative **KSh 129.46/USD** rate shown on 22 September 2026 ([CBK indicative rates](https://www.centralbank.go.ke/cbk-indicative-rates/)). USD-based bills may be charged at the card/bank's exchange rate and can incur bank fees or tax. Render sizes/prices and included features can change; the sample database and cache tiers are starting assumptions, not a guaranteed capacity recommendation. Review [Render pricing](https://render.com/pricing) for the current plan details. Vercel Pro's included usage credit applies to eligible Vercel usage; it does not pay Render, SMS, or M-Pesa bills. Vercel lists taxes separately where applicable. MapTiler pricing includes 25,000 map sessions on Flex; verify its current quota and key restrictions before launch.

The subtotal excludes:

- SMS delivery and transactional sender-ID setup.
- Safaricom merchant charges, reversals, or other PayBill costs.
- Domain renewal (the cited KSh 1,160/year is about KSh 97/month when spread across a year).
- R2 storage/operations after the free tier, which is likely KSh 0 at early scale but depends on usage.
- VAT/tax, bank exchange fees, backups beyond the selected plan, support staff, legal/accounting, marketing, and any paid monitoring.
- Additional hosting usage, traffic/bandwidth, or extra team seats.

With 1,000 SMS and domain renewal spread monthly, plan for about **KSh 17,156/month plus Safaricom's actual charges**. The approximate first month with the cited domain and bundled Safaricom+Airtel sender-ID setup is **KSh 32,319 plus Safaricom merchant charges**. This uses the historical sender-ID figure and excludes taxes/fees that need confirmation.

For an early pilot, providers may offer smaller/free tiers, but free plans can have non-commercial restrictions, expire, sleep, lack backups, or have limited support. Do not present a free developer setup as a reliable commercial production budget. Local Docker services incur no hosted-service invoice but depend on the owner's computer, power, and internet and are not the production hosting plan.

## 5. Example monthly operating arithmetic

For illustration only, suppose 100 tenants each buy the 3-request bundle (KSh 10,000 collected) and 30 rentals complete at an average landlord fee of KSh 1,500 (KSh 45,000 collected). Combined gross collections are **KSh 55,000**. At 1,000 SMS, allow about KSh 928; with the hypothetical 0.5% merchant-rate scenario, the transaction fee would be KSh 275. Subtract the estimated KSh 16,131 hosting/map subtotal and KSh 97 monthly domain allocation: about **KSh 37,569 remains before taxes, salaries, support, marketing, refunds, charge discrepancies, and other costs**. Tenant bundle payments for unused credits may be unearned/deferred revenue until the service is delivered; ask an accountant how to recognize it.

This is a teaching example only. It does not establish expected sales, the real average landlord fee, actual Safaricom charges, accounting revenue, or profit. Replace each assumption with measured monthly activity and written supplier prices. Each Safaricom tariff must be confirmed; the 0.5% rate is not a quote.

## 6. One-time launch and setup costs

| Setup item | Planning note |
|---|---|
| Domain | Example `.co.ke` KSh 1,160/year at the cited registrar; check renewal rate and ownership account. |
| Africa's Talking sender ID | 2025 price-sheet examples KSh 4,500–14,100 depending on network; re-quote and confirm VAT. |
| Safaricom merchant onboarding | Application, business documents, approval, shortcode and tariff depend on Safaricom's requirements and agreement. No fixed project quote is available. |
| Production deployment/configuration | Engineering time to configure secrets, HTTPS, database migrations, monitoring, backups, callbacks and scheduled notifications. This is labor rather than a listed provider fee. |
| Business/legal/tax setup | Not estimated here; obtain local professional advice and budget separately. |

## 7. Current implementation and what remains before launch

The repository documents that Daraja, Africa's Talking, and R2 integrations require real provider credentials/settings to work live. The viewing-credit payment flow and nearby discovery are now included in the application code; they still require a live Safaricom configuration. The app's hourly SMS outbox/reminder command must also be scheduled in production. The repository's `docker-compose.yml` is for local development; it is not a paid production hosting service. The map defaults to OpenStreetMap tiles for local preview; configure a restricted `NEXT_PUBLIC_MAPTILER_KEY` and use the commercial plan for production.

Before announcing payments as live, verify all of these:

1. Safaricom merchant account and **written PayBill tariff** approved for the exact STK Push flow.
2. Production Daraja credentials, publicly reachable HTTPS callback, callback secret, and end-to-end low-value test plus reconciliation.
3. Africa's Talking account, current SMS quote, sender ID approval, and a test for OTP plus viewing updates.
4. Production database backups, restore test, access control, and monitoring.
5. R2 bucket credentials, private upload/signing configuration, image delivery, and storage lifecycle/retention choice.
6. Customer-facing success-fee schedule, receipt/support process, and agreed refund/dispute handling.
7. Monthly dashboard tracking confirmed rentals, collected fees, M-Pesa charges, SMS segments, failed deliveries, refunds, and provider invoices.

## Public pricing and product references

- [Safaricom Daraja developer portal](https://developer.safaricom.co.ke/)
- [Safaricom PayBill FAQ](https://www.safaricom.co.ke/media-center-landing/frequently-asked-questions/m-pesa-paybill?tmpl=component)
- [Safaricom published M-Pesa Business Till tariff (not the project's PayBill quote)](https://www.safaricom.co.ke/images/Downloads/the-m-pesa-business-till-tariff.pdf)
- [Africa's Talking Kenya Bulk SMS pricing](https://help.africastalking.com/en/articles/12381163-bulk-sms-kenya)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Render pricing](https://render.com/pricing)
- [Render PostgreSQL extensions / PostGIS compatibility](https://render.com/docs/postgresql-extensions)
- [Vercel pricing](https://vercel.com/pricing) and [Hobby plan terms](https://vercel.com/docs/plans/hobby)
- [Safaricom Domains pricing](https://domains.safaricom.co.ke/index.php?rp=%2Fdomain%2Fpricing)
- [Central Bank of Kenya indicative exchange rates](https://www.centralbank.go.ke/cbk-indicative-rates/)
