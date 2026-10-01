import type { LegalDoc } from "./types";

export const copyright: LegalDoc = {
  slug: "copyright",
  title: "Copyright & Intellectual Property",
  description: "Who owns what on Nyumbani: the platform, user content and third-party content.",
  sections: [
    {
      id: "platform",
      heading: "1. Platform intellectual property",
      body: [
        "© {{year}} Erip Software. All rights reserved. This notice covers the Service’s own software, design, name, logo and text created for it. Please do not copy or reuse them without written permission, except as the law allows.",
      ],
    },
    {
      id: "user",
      heading: "2. User-generated content",
      body: [
        "Listing descriptions, photos, messages, notes and profile information belong to the people who create them. The copyright notice above does not claim ownership of that content. Users give us a licence to host and display it so the Service can work, as set out in the Terms.",
      ],
    },
    {
      id: "third",
      heading: "3. Third-party content and services",
      body: [
        "Maps, fonts, SMS and payment services, and any other third-party material belong to their respective owners and are used under their terms. Map data © OpenStreetMap contributors where shown.",
      ],
    },
    {
      id: "report",
      heading: "4. Reporting infringement",
      body: [
        "If you believe content on the Service infringes your rights, contact {{contactEmail}} with details of the content and your claim. You can also use “Report this listing” on a listing page.",
      ],
    },
  ],
};
