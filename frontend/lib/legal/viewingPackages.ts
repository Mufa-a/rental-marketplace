import type { LegalDoc } from "./types";

export const viewingPackages: LegalDoc = {
  slug: "viewing-packages",
  title: "Viewing Packages, Fees & Refunds",
  description: "What tenants pay for viewing packages, what landlords pay when a viewing becomes a tenancy, and how refunds work.",
  intro: "Nyumbani does not collect rent or deposits. These are the only things we charge for. Current prices are shown above and at checkout; we may change them, but a change never affects a payment you have already made.",
  sections: [
    { id: "packages", heading: "1. Tenant viewing packages", body: [
      { list: [
        "Browsing, searching and saving homes is free.",
        "A package buys viewing-request credits. One credit is set aside when you send a request and is used only when the landlord approves the viewing.",
        "Your credit is returned automatically if the landlord declines, the request expires unanswered after 7 days, you cancel before approval, the landlord cancels an approved viewing, or the home is taken off the market before approval.",
        "If you cancel a viewing after the landlord has approved it, the credit is used.",
        "Credits do not expire and can be used for any listing in the same country.",
        "A package is not rent, a deposit, a booking fee or a guarantee that a landlord will approve a viewing or let you the home.",
      ] },
    ] },
    { id: "landlord-fees", heading: "2. Landlord success fees", body: [
      { list: [
        "Listing homes and receiving viewing requests is free for landlords.",
        "A one-off success fee is due only when a tenant you met through a viewing arranged on Nyumbani rents the home within {{referralWindow}} days of that viewing.",
        "The fee depends on the agreed monthly rent and follows the bands shown above. It is calculated when the rental is recorded and does not change afterwards.",
        "The fee is due within 7 days. If you believe a fee is wrong, contact us before the due date; we review the viewing records with both sides and can waive it.",
        "Optional services such as property verification are priced separately and shown before you pay.",
      ] },
    ] },
    { id: "payments", heading: "3. How payments work", body: [
      { list: [
        "Payments are made by M-Pesa. You approve a prompt on your own phone; we never ask for your M-Pesa PIN.",
        "A payment counts only after Safaricom confirms it to our servers. If no confirmation arrives within about 10 minutes, the payment is shown as not completed; if money did leave your account, it is matched automatically or by our team using your M-Pesa message.",
        "Each M-Pesa receipt can settle only one purchase. Repeated taps or retries never charge you twice for the same order.",
      ] },
    ] },
    { id: "refunds", heading: "4. Refunds", body: [
      { list: [
        "Unused viewing credits: you can ask for a refund of a package from which no credit has been used, within 30 days of purchase. Partially used packages are not refunded, except where the law requires it.",
        "Duplicate or failed charges: if you were charged without receiving what you paid for, we refund the full amount once confirmed.",
        "Success fees: refunded or waived if our review finds the tenancy did not result from a Nyumbani viewing.",
        "Refunds are sent back to the M-Pesa number that paid, normally within 7 working days of approval. Refunded credits or services are removed from your account.",
        "Final refund terms: {{refundPolicy}}.",
      ] },
    ] },
  ],
};
