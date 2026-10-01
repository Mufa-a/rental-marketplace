import type { LegalDoc } from "./types";

export const terms: LegalDoc = {
  slug: "terms",
  title: "Terms & Conditions",
  description: "The rules for using Nyumbani as a tenant, landlord or visitor.",
  intro:
    "These terms explain how Nyumbani works and what you can expect from us and from other users. Please read them before creating an account. This is a product draft that has not yet been reviewed by a lawyer.",
  sections: [
    {
      id: "acceptance",
      heading: "1. Acceptance of these terms",
      body: [
        "By creating an account or using {{brand}} (the “Service”), you agree to these Terms & Conditions and acknowledge the Privacy Policy. If you do not agree, please do not use the Service.",
        "The Service is operated and developed under {{operator}}. The registered legal entity is: {{legalEntityName}}.",
      ],
    },
    {
      id: "eligibility",
      heading: "2. Eligibility",
      body: [
        "You may use the Service only if you can enter into a binding rental-related arrangement under the laws that apply to you, and you are not barred from using it by any law.",
        { note: "Minimum age and any other eligibility rule must be confirmed by the platform owner and legal counsel before publishing." },
      ],
    },
    {
      id: "accounts",
      heading: "3. Accounts",
      body: [
        "You sign in with a Kenyan mobile phone number. You are responsible for keeping access to that number and your signed-in devices secure, and for everything done through your account.",
        "Give us accurate information and keep it up to date. One person should not share an account with others.",
      ],
    },
    {
      id: "verification",
      heading: "4. One-time codes and account verification",
      body: [
        "We verify your phone number by sending a one-time code by SMS. Codes expire after five minutes and can be used once. Repeated wrong attempts temporarily lock further attempts.",
        "Never share a code with anyone. We will never ask you for one. A verified phone number confirms that you control that number; it is not a check of your identity or of the accuracy of anything you post.",
      ],
    },
    {
      id: "responsibilities",
      heading: "5. Your responsibilities",
      body: [
        "Use the Service lawfully and honestly. You are responsible for what you post and for what you do offline as a result of using the Service, including any viewing, agreement or payment you make with another person.",
      ],
    },
    {
      id: "tenants",
      heading: "6. Tenant responsibilities",
      body: [{
        list: [
          "Request viewings only for homes you are genuinely interested in.",
          "Attend approved viewings on time, or cancel in advance through the Service.",
          "Report the outcome of a viewing honestly when asked.",
          "Do not pay anyone before you have seen the home and are satisfied it is genuine.",
        ],
      }],
    },
    {
      id: "landlords",
      heading: "7. Landlord responsibilities",
      body: [{
        list: [
          "You must be entitled to let or advertise every home you list, or be authorised by the person who is.",
          "Respond to viewing requests promptly and honour approved viewings.",
          "Confirm availability regularly and mark homes as not available when they are let.",
          "Report the outcome of a viewing honestly, including when a home is rented.",
        ],
      }],
    },
    {
      id: "listings",
      heading: "8. Listing requirements",
      body: [
        "Each listing must describe a real home that you are entitled to advertise, with a monthly rent that is the actual rent, and with photos of that home. Listings that are not confirmed as available for 30 days stop appearing in search until the landlord confirms again.",
      ],
    },
    {
      id: "accuracy",
      heading: "9. Accuracy of property information",
      body: [
        "Listing information is provided by landlords. We do not inspect homes and do not guarantee that any listing is accurate, complete or up to date. Verification labels, where shown, describe the status recorded in the Service and are not a guarantee.",
        "Check the details yourself, in person, before you commit to anything.",
      ],
    },
    {
      id: "viewing-requests",
      heading: "10. Viewing requests and bundles",
      body: [
        "A tenant asks for a viewing through the Service and the landlord approves or declines it. Browsing is free. Requesting a viewing uses a viewing credit from a bundle you buy by M-Pesa; bundle sizes and prices are shown in the app at the time of purchase.",
        "A credit is reserved when you request a viewing. It is used up if the landlord approves, and is returned if the landlord declines, you cancel before approval, or the request expires unanswered.",
        "After a rental that started from a viewing on the Service is confirmed, the landlord owes a success fee, shown in the app before payment. Refunds for bundles or fees: {{refundPolicy}}.",
      ],
    },
    {
      id: "booking",
      heading: "11. Booking and viewing procedures",
      body: [
        "The Service records each request, the landlord’s response, the scheduled time, and the outcome reported by the tenant and landlord, with timestamps. These records help both sides and are used to resolve disagreements.",
        "If the tenant and landlord report different outcomes, the viewing is marked as disputed and may be reviewed by the platform administrators.",
      ],
    },
    {
      id: "cancellation",
      heading: "12. Cancellation",
      body: [
        "A tenant may cancel a pending or approved request through the Service. A landlord may decline a pending request. Please cancel as early as you can so the other person is not left waiting.",
      ],
    },
    {
      id: "availability",
      heading: "13. Property availability",
      body: [
        "A home can be rented, withdrawn or changed at any time. The “Available” label means the landlord recently confirmed availability in the Service; it is not a promise that the home will still be free when you view it.",
      ],
    },
    {
      id: "role",
      heading: "14. Our role as an intermediary",
      body: [
        "{{brand}} is an online platform that helps tenants find homes and lets landlords receive and manage viewing requests. We are not the owner, landlord, tenant, real estate agent or guarantor of any home, and we are not a party to any tenancy or other agreement between users. Rent, deposits and the lease are agreed directly between the tenant and landlord.",
      ],
    },
    {
      id: "no-guarantee",
      heading: "15. No guarantee of a rental",
      body: [
        "We do not guarantee that a viewing will be approved or take place, that any home will be suitable, or that a rental will result from using the Service.",
      ],
    },
    {
      id: "prohibited",
      heading: "16. Prohibited activities",
      body: [{
        list: [
          "Posting false, misleading or unlawful content.",
          "Using another person’s phone number, identity or property without permission.",
          "Trying to access other users’ accounts or data, or to interfere with the Service or its security.",
          "Scraping or copying the Service at scale without our written permission.",
          "Using the Service to send spam or unsolicited promotions.",
        ],
      }],
    },
    {
      id: "fraud",
      heading: "17. Fraudulent listings",
      body: [
        "Listing a home that does not exist, that you are not entitled to let, or that you do not intend to let on the stated terms is prohibited. Asking anyone for payment before a genuine viewing, or asking for payment outside the Service in order to “reserve” a home, is a sign of fraud. We may remove listings, suspend accounts and, where appropriate, report suspected fraud to the authorities.",
      ],
    },
    {
      id: "misrepresentation",
      heading: "18. Misrepresentation",
      body: [
        "Do not misrepresent who you are, the condition, rent, location or availability of a home, or the outcome of a viewing.",
      ],
    },
    {
      id: "harassment",
      heading: "19. Harassment and abuse",
      body: [
        "Treat other users with respect. Harassment, threats, discrimination and abusive language are not allowed and may lead to suspension.",
      ],
    },
    {
      id: "circumvention",
      heading: "20. Circumventing the platform",
      body: [
        "Viewings for homes found on the Service should be requested and recorded through the Service. Please do not use the Service to identify a home and then deliberately arrange that viewing elsewhere in order to avoid the Service’s fees or records.",
        "This does not restrict you from agreeing rent, deposits or the lease directly with the other party once you have viewed the home through the Service.",
      ],
    },
    {
      id: "ip",
      heading: "21. Intellectual property",
      body: [
        "The Service’s own software, design, name and branding belong to {{operator}} or its licensors. © Erip Software. All rights reserved. You may not copy or reuse them without permission, except as the law allows.",
        "Content uploaded by users and third-party content are not owned by us; see the next two sections and the Copyright page.",
      ],
    },
    {
      id: "ugc",
      heading: "22. User-generated content",
      body: [
        "You keep ownership of what you post, including property descriptions, photos, notes and profile information. You are responsible for it and confirm that you have the right to post it.",
        "You give {{operator}} a non-exclusive licence to host, display and process that content so we can operate the Service (for example, showing your listing photos in search results). We may remove content that breaks these terms. You can report a listing from its page.",
        { note: "The scope, duration and territory of this licence should be confirmed by counsel." },
      ],
    },
    {
      id: "platform-content",
      heading: "23. Platform content",
      body: [
        "Text, layouts and other material that we create for the Service is platform content and is protected as described above. Property listings, photos and descriptions posted by landlords are user-generated content, not platform content.",
      ],
    },
    {
      id: "third-party",
      heading: "24. Third-party services",
      body: [
        "The Service relies on third-party providers, for example for SMS delivery, M-Pesa payments, photo storage, fonts and map tiles. We do not control them, and their own terms and policies apply when you interact with them. We are not responsible for their services.",
      ],
    },
    {
      id: "suspension",
      heading: "25. Suspension and termination",
      body: [
        "We may suspend or end an account, remove content or limit features if we reasonably believe these terms have been broken, to protect other users, or where the law requires. A suspended account cannot be re-enabled by requesting a new one-time code. You may stop using the Service at any time and may ask us to delete your account (see the Privacy Policy).",
      ],
    },
    {
      id: "disclaimers",
      heading: "26. Disclaimers",
      body: [
        "The Service is provided “as is” and “as available”. To the extent the law allows, we do not promise that it will be uninterrupted, error-free or that any listing or user is trustworthy.",
        { note: "Wording of disclaimers and what may legally be excluded must be reviewed by counsel." },
      ],
    },
    {
      id: "liability",
      heading: "27. Limitation of liability",
      body: [
        "To the extent the law allows, {{operator}} is not liable for losses arising from dealings between users, from inaccurate listings, or from a rental that does or does not go ahead. Nothing in these terms excludes liability that cannot be excluded by law.",
        { note: "The extent of the limitation, and any cap, must be decided with legal counsel." },
      ],
    },
    {
      id: "indemnity",
      heading: "28. Indemnification",
      body: [
        "Where the law allows, you agree to compensate us for losses we suffer because of your unlawful use of the Service or your breach of these terms.",
        { note: "Whether and how far this clause is enforceable must be confirmed by counsel." },
      ],
    },
    {
      id: "service-changes",
      heading: "29. Changes to the Service",
      body: [
        "We may add, change or remove features, prices and bundles. Where a change materially affects you, we will try to tell you in advance.",
      ],
    },
    {
      id: "terms-changes",
      heading: "30. Changes to these terms",
      body: [
        "We may update these terms. The version and “last updated” date are shown at the top of this page. If we make material changes we will ask you to review them and, where needed, to agree again.",
      ],
    },
    {
      id: "law",
      heading: "31. Governing law",
      body: ["These terms are governed by: {{governingLaw}}."],
    },
    {
      id: "disputes",
      heading: "32. Dispute resolution",
      body: [
        "Please contact us first so we can try to resolve a complaint. Formal dispute resolution: {{disputeResolution}}.",
        "Disagreements between a tenant and a landlord about a viewing outcome can be raised through the Service’s dispute process.",
      ],
    },
    {
      id: "contact",
      heading: "33. Contact",
      body: [
        "Contact us at {{contactEmail}} or {{contactPhone}}. Address: {{registeredAddress}}. You can also use the Contact page.",
      ],
    },
  ],
};
