import type { LegalDoc } from "./types";

export const dataProtection: LegalDoc = {
  slug: "data-protection",
  title: "Data Protection Information",
  description: "How Nyumbani approaches personal data protection, and what still needs confirmation.",
  intro:
    "A plain-language summary of how personal information is protected in the Service, your practical choices, and what the operator still has to confirm. It supplements the Privacy Policy.",
  sections: [
    {
      id: "status",
      heading: "1. Legal status of this page",
      body: [
        "The Service may be subject to data protection law in Kenya and in other places where its users live. The operator has not yet confirmed which laws apply, and nothing on this site should be read as a statement that the Service is compliant with any specific law.",
        { note: "Applicable jurisdictions and obligations (including any registration, data protection officer or impact-assessment requirements) must be reviewed by a qualified Kenyan or privacy lawyer." },
      ],
    },
    {
      id: "controller",
      heading: "2. Who is responsible",
      body: [
        "Operator: {{operator}}. Registered legal entity: {{legalEntityName}}. Data protection contact: {{dpoContact}}. Email: {{contactEmail}}.",
      ],
    },
    {
      id: "principles",
      heading: "3. How the Service is built",
      body: [
        { list: [
          "Only the information needed to run the marketplace is collected; identity documents are not requested.",
          "Users can reach only their own records; landlords and tenants cannot see each other’s private details.",
          "Phone numbers are masked on the administrator dashboard and administrator access to it is logged.",
          "Your agreement to the Terms and Privacy Policy is recorded with the version, and optional choices are recorded separately.",
          "You can ask for your account to be deleted; a person reviews each request.",
        ] },
      ],
    },
    {
      id: "your-choices",
      heading: "4. Your choices",
      body: [
        { list: [
          "Update your name and email in your profile at any time.",
          "Use location search only if you want to; it is off by default.",
          "Request account deletion from your profile.",
          "Contact us to ask about, correct or object to the use of your information. Which rights apply depends on the law that applies to you.",
        ] },
      ],
    },
    {
      id: "processors",
      heading: "5. Service providers",
      body: [
        "Africa’s Talking (SMS), Safaricom M-Pesa (payments), Cloudflare R2 (photo storage), and {{hostingProvider}} (hosting). See the Privacy Policy for what each receives. Data location: {{internationalTransfers}}.",
      ],
    },
    {
      id: "complaints",
      heading: "6. Complaints",
      body: [
        "Please contact us first at {{contactEmail}}. Where a data protection law applies to you, you may also complain to the relevant authority; in Kenya this is the Office of the Data Protection Commissioner.",
      ],
    },
  ],
};
