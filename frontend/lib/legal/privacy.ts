import type { LegalDoc } from "./types";

/**
 * Every statement about data collection below was checked against the application code
 * (backend models/serializers and frontend components). If a feature changes what is
 * collected, update this file in the same change.
 */
export const privacy: LegalDoc = {
  slug: "privacy",
  title: "Privacy Policy",
  description: "What personal information Nyumbani collects, why, who sees it, and your choices.",
  intro:
    "This policy describes what personal information the Service actually handles today. It is a product draft that has not yet been reviewed by a lawyer or privacy professional, and it does not claim that the Service complies with any particular law.",
  sections: [
    {
      id: "who",
      heading: "1. Who we are",
      body: [
        "{{brand}} is operated and developed under {{operator}} (registered legal entity: {{legalEntityName}}). Contact: {{contactEmail}}. Data protection contact: {{dpoContact}}.",
      ],
    },
    {
      id: "collect",
      heading: "2. Information we collect",
      body: [
        { sub: "Account data" },
        { list: [
          "Your mobile phone number (required) and the role you chose: tenant or landlord.",
          "Optional profile details you add: first name, last name and email address.",
          "Sign-in security data: one-time codes are stored only in scrambled (hashed) form and expire after five minutes; we do not store passwords for phone sign-in.",
          "Whether your phone number has been verified, and when your account was created.",
        ] },
        { sub: "Tenant data" },
        { list: [
          "Viewing requests you make (the home, an optional message, and any preferred times), the landlord’s response, and the scheduled viewing.",
          "Outcomes you report after a viewing (for example rented or did not rent) and any note you add.",
          "Homes you save.",
          "Viewing bundle purchases: the phone number you pay from, the amount and the M-Pesa receipt reference.",
        ] },
        { sub: "Landlord data" },
        { list: [
          "The same account data as above, and the properties and units you list: name, description, address, area, city, rent, deposit, bedrooms, amenities, availability, photos.",
          "Viewing requests received for your listings, your responses and outcomes you report.",
          "Success fees that become due and their payments (payer phone number, amount, M-Pesa receipt reference).",
        ] },
        { sub: "Property data" },
        "Address, area and city; optional map coordinates you provide for a property; photos (the browser removes hidden photo metadata such as GPS tags before upload); price; amenities; availability and descriptions.",
        { sub: "Technical data" },
        { list: [
          "Your IP address and request timestamps, which our servers use for security and to limit abuse (for example rate limits). Web server and hosting logs may also record them.",
          "Browser and device information sent with normal web requests.",
          "A sign-in session stored in your browser (see the Cookie Policy).",
        ] },
        { sub: "Reports, consent and account records" },
        { list: [
          "Reports you file about listings, and disputes over viewing outcomes.",
          "A record of what you agreed to, which version of these documents you saw, and when.",
          "Any account deletion request you file.",
          "An audit log of important actions (who did what, to which record, and when).",
        ] },
      ],
    },
    {
      id: "not-collected",
      heading: "3. What the Service does not currently collect",
      body: [
        { list: [
          "Identity documents, tenancy agreements or other uploaded documents. The Service currently accepts property photos only.",
          "Your location history. Location is used only when you choose “Homes near me” (see section 8).",
          "Analytics or advertising trackers.",
        ] },
        "If this changes, we will update this policy and, where required, ask for your consent first.",
      ],
    },
    {
      id: "purposes",
      heading: "4. Why we use your information",
      body: [
        { list: [
          "To create and secure your account and verify your phone number.",
          "To provide the marketplace: show listings, process viewing requests, schedule viewings and record outcomes.",
          "To send you service messages by SMS, such as verification codes, viewing approvals and reminders.",
          "To take and record M-Pesa payments for viewing bundles and success fees.",
          "To prevent fraud and abuse, keep the Service secure and investigate reports and disputes.",
          "To keep the records needed to run the Service and to handle support requests.",
          "To meet legal obligations where they apply.",
        ] },
        "We do not currently send marketing messages. If we introduce them, they will be optional and separate from creating an account.",
      ],
    },
    {
      id: "basis",
      heading: "5. Legal grounds",
      body: [
        { note: "The legal grounds for processing (for example contract, consent, legitimate interest, legal obligation) depend on the applicable law and must be confirmed by counsel." },
        "Jurisdictions the Service is offered in: {{jurisdictions}}.",
      ],
    },
    {
      id: "sharing",
      heading: "6. Who can see your information",
      body: [
        { sub: "Visible to other marketplace users" },
        { list: [
          "Public listing pages show a home’s title, description, rent, photos, amenities, area and city, its verification label and an approximate map pin (rounded so it does not show the exact entrance). They do not show the landlord’s name or phone number.",
          "A landlord can see the viewing requests for their own homes, including the tenant’s optional message and preferred times. A tenant can see the landlord’s response, the scheduled time and meeting note for their own requests.",
          "The Service does not display your phone number to the other party. Anything you type into a message or note can be read by the other party to that request, so avoid sharing details you do not need to.",
        ] },
        { sub: "Private" },
        { list: [
          "Your phone number, email, name, payment details, saved homes and consent history are not shown to other users.",
          "A landlord cannot see other landlords’ listings or requests, and a tenant cannot see other tenants’ requests.",
        ] },
        { sub: "Platform administrators" },
        "A small number of administrators can review users, viewing requests, payments, reports and disputes to run the Service and handle support. Their dashboard masks phone numbers, and access to the administrator dashboard is logged.",
      ],
    },
    {
      id: "providers",
      heading: "7. Service providers we use",
      body: [
        "We share the minimum needed with providers that help us run the Service. They receive information only to perform their service, and their own policies also apply.",
        { list: [
          "SMS delivery (Africa’s Talking): your phone number and the message text, for verification codes and notifications.",
          "Payments (Safaricom M-Pesa): the phone number you pay from and the amount.",
          "Photo storage (Cloudflare R2): the property photos landlords upload.",
          "Hosting and database: {{hostingProvider}}.",
          "Fonts (Google Fonts): your browser requests fonts from Google when a page loads, which shares your IP address and browser details with them.",
          "Maps: only when you open the nearby map, your browser loads a map library from unpkg and map tiles from MapTiler (if configured) or OpenStreetMap, which share your IP address and the map area you view.",
        ] },
        "We do not sell your personal information.",
      ],
    },
    {
      id: "location",
      heading: "8. Location information",
      body: [
        { list: [
          "What: if you press “Homes near me”, your browser asks permission and, if you agree, sends your approximate coordinates to our server so we can list nearby homes and sort them by distance.",
          "Why: only to show nearby homes. It is optional; you can search by area instead.",
          "Storage: we do not save your coordinates in your account or database. They are used for that search request, and the search result (not your identity) may be held briefly in a short-lived cache so repeat searches are fast.",
          "Control: you can decline or later withdraw location permission in your browser or device settings. The Service still works without it.",
          "Landlords may enter map coordinates for their own properties; these are stored with the property and shown publicly only as an approximate pin.",
        ] },
      ],
    },
    {
      id: "retention",
      heading: "9. How long we keep information",
      body: [
        "Different kinds of information are kept for different periods. The periods below are set by the platform owner and are configuration values, not final commitments until published.",
        { list: [
          "Account and profile data: {{retentionAccount}}.",
          "Viewing requests and outcomes: {{retentionViewings}}.",
          "Payment and fee records: {{retentionPayments}}.",
          "Audit logs: {{retentionAudit}}.",
          "Reports and disputes: {{retentionReports}}.",
          "Expired verification codes: {{retentionOtp}}.",
        ] },
      ],
    },
    {
      id: "security",
      heading: "10. How we protect information",
      body: [
        "We use measures such as scrambled storage of one-time codes, short-lived sign-in tokens, access checks so users can only reach their own records, rate limiting, and encrypted connections (HTTPS) in production. No system is completely secure, so we cannot guarantee absolute security. Please keep your phone and one-time codes private.",
      ],
    },
    {
      id: "rights",
      heading: "11. Your rights",
      body: [
        "Depending on the law that applies to you, you may have the right to ask to access your information, correct it, delete it, object to certain uses, withdraw consent you gave, receive a copy of information you provided, and complain to your data protection authority. Which rights apply, and their limits, depend on applicable law; not every right applies in every place.",
        "To make a request, use the Contact page or, for deletion, the option in your profile.",
      ],
    },
    {
      id: "deletion",
      heading: "12. Deleting your account",
      body: [
        "You can ask us to delete your account from your profile. You are asked to confirm by typing your phone number, and you see what will happen first. Requests are reviewed by an administrator; deletion is not instant.",
        "Some records, such as payment and fee records and audit logs of viewings, may need to be kept for accounting, fraud-prevention or legal reasons, even after your profile is removed. Active viewing requests are closed, and any listings are taken down.",
      ],
    },
    {
      id: "consent",
      heading: "13. Consent",
      body: [
        "When you create an account you agree to the Terms & Conditions and acknowledge this Privacy Policy. We record that agreement with the version and time. Optional things, such as location search, are separate and are never bundled into that agreement.",
      ],
    },
    {
      id: "children",
      heading: "14. Children",
      body: [
        "The Service is not intended for children. Do not create an account if you are not old enough to rent or advertise a home under the law that applies to you.",
        { note: "The minimum age must be confirmed by counsel." },
      ],
    },
    {
      id: "transfers",
      heading: "15. Where information is stored",
      body: ["Data location and any transfers outside Kenya: {{internationalTransfers}}."],
    },
    {
      id: "changes",
      heading: "16. Changes to this policy",
      body: [
        "We will update the version and “last updated” date whenever this policy changes, and ask for your agreement again where the change is significant.",
      ],
    },
    {
      id: "contact",
      heading: "17. Contact and complaints",
      body: [
        "Questions or requests: {{contactEmail}}. Data protection contact: {{dpoContact}}.",
        "Where a data protection law applies to you, you may also have the right to complain to the data protection authority for your country. In Kenya, this is the Office of the Data Protection Commissioner.",
      ],
    },
  ],
};
