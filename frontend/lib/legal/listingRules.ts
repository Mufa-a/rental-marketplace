import type { LegalDoc } from "./types";

export const listingRules: LegalDoc = {
  slug: "listing-rules",
  title: "Listing Rules",
  description: "What landlords must and must not do when listing a home on Nyumbani, and how we moderate listings.",
  intro: "These rules keep listings honest so tenants can trust what they see. They form part of the Terms & Conditions. Breaking them can lead to a listing being removed or an account being suspended.",
  sections: [
    { id: "real", heading: "1. List only real, available homes", body: [
      { list: [
        "The home must exist, be available to let on the stated terms, and you must own it or be authorised by the owner to let it.",
        "List each unit once. Do not copy another landlord's listing or photos. Listings that match another landlord's listing, or that reuse another landlord's photos, are held for review before they appear in search.",
        "Confirm availability at least every 30 days. Unconfirmed listings are hidden from search automatically until you confirm them.",
        "Mark a home as occupied as soon as it is let. Open viewing requests are then closed and tenants' credits returned.",
      ] },
    ] },
    { id: "accurate", heading: "2. Be accurate", body: [
      { list: [
        "Show the full monthly rent and deposit you will actually charge. Do not add undisclosed fees.",
        "Use recent photos of the actual unit. Stock or borrowed photos are not allowed.",
        "Describe the location honestly (estate, town, county). The exact street address is shared with a tenant only when you approve their viewing.",
      ] },
    ] },
    { id: "payments", heading: "3. No payments before a viewing", body: [
      "Never ask a tenant for a deposit, “booking fee”, “viewing fee” or any other payment before they have viewed the home. Asking for money outside the agreed rental process is a common scam pattern and leads to removal.",
    ] },
    { id: "viewings", heading: "4. Viewings and referral fees", body: [
      { list: [
        "Reply to viewing requests within 7 days. Unanswered requests expire and the tenant's credit is returned.",
        "If you need to cancel an approved viewing, do it before the agreed time; the tenant's credit is returned.",
        "After a viewing, report the outcome honestly. If a tenant you met through a Nyumbani viewing rents the home within the attribution period ({{referralWindow}} days), the platform success fee applies. Arranging the tenancy off-platform to avoid the fee breaches these rules.",
        "When records disagree (for example a tenant reports renting and you do not), our team contacts both sides and decides based on the evidence. You can contest a fee before its due date.",
      ] },
    ] },
    { id: "moderation", heading: "5. How we moderate", body: [
      { list: [
        "We may review any listing before or after it is published, and ask for changes, reject it, or take it offline while we check it.",
        "When several different users report a listing for fraud, fake photos, misleading prices or unavailability, it is taken offline automatically until reviewed.",
        "Verification badges mean our team checked documents for the property or the landlord's identity. They are not a guarantee that a landlord or home is legitimate, and they do not replace a tenant's own checks.",
      ] },
    ] },
  ],
};
