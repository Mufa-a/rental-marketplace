/**
 * Legal configuration — the ONE place the platform owner fills in real details.
 *
 * Nothing here is invented. Any value that has not been provided is rendered on
 * the legal pages as a clearly highlighted "[TO BE PROVIDED: …]" placeholder, so
 * an unfinished draft can never be mistaken for real company details.
 *
 * Values are read from NEXT_PUBLIC_LEGAL_* environment variables (see
 * frontend/.env.local.example) so the owner does not need to edit code.
 * Keep LEGAL_VERSION in sync with LEGAL_POLICY_VERSION in the backend settings.
 */

/** Bump when the Terms or Privacy Policy change in a way users should re-accept. */
export const LEGAL_VERSION = process.env.NEXT_PUBLIC_LEGAL_VERSION ?? "draft-1";

/** "draft" shows a visible banner on every legal page. Set to "published" only after legal review. */
export const LEGAL_STATUS: "draft" | "published" =
  process.env.NEXT_PUBLIC_LEGAL_STATUS === "published" ? "published" : "draft";

/** Product/brand shown to users. */
export const BRAND_NAME = "Nyumbani";
/** The organisation the platform is operated/developed under (as provided by the owner). */
export const OPERATOR_NAME = "Erip Software";

type Field = { label: string; value: string | undefined };

const FIELDS: Record<string, Field> = {
  legalEntityName: { label: "registered legal entity name", value: process.env.NEXT_PUBLIC_LEGAL_ENTITY_NAME },
  registeredAddress: { label: "registered business address", value: process.env.NEXT_PUBLIC_LEGAL_ADDRESS },
  contactEmail: { label: "official contact email", value: process.env.NEXT_PUBLIC_LEGAL_CONTACT_EMAIL },
  contactPhone: { label: "official contact phone number", value: process.env.NEXT_PUBLIC_LEGAL_CONTACT_PHONE },
  dpoContact: { label: "data protection contact / officer, if applicable", value: process.env.NEXT_PUBLIC_LEGAL_DPO_CONTACT },
  jurisdictions: { label: "jurisdictions the service is offered in", value: process.env.NEXT_PUBLIC_LEGAL_JURISDICTIONS },
  governingLaw: { label: "governing law", value: process.env.NEXT_PUBLIC_LEGAL_GOVERNING_LAW },
  disputeResolution: { label: "dispute-resolution process", value: process.env.NEXT_PUBLIC_LEGAL_DISPUTE_RESOLUTION },
  refundPolicy: { label: "refund policy for viewing bundles and fees", value: process.env.NEXT_PUBLIC_LEGAL_REFUND_POLICY },
  hostingProvider: { label: "hosting provider", value: process.env.NEXT_PUBLIC_LEGAL_HOSTING_PROVIDER },
  internationalTransfers: { label: "where personal data is stored and any transfers outside Kenya", value: process.env.NEXT_PUBLIC_LEGAL_DATA_LOCATION },
  retentionAccount: { label: "retention period for account and profile data", value: process.env.NEXT_PUBLIC_LEGAL_RETENTION_ACCOUNT },
  retentionViewings: { label: "retention period for viewing requests and outcomes", value: process.env.NEXT_PUBLIC_LEGAL_RETENTION_VIEWINGS },
  retentionPayments: { label: "retention period for payment and fee records", value: process.env.NEXT_PUBLIC_LEGAL_RETENTION_PAYMENTS },
  retentionAudit: { label: "retention period for audit logs", value: process.env.NEXT_PUBLIC_LEGAL_RETENTION_AUDIT },
  retentionReports: { label: "retention period for reports and disputes", value: process.env.NEXT_PUBLIC_LEGAL_RETENTION_REPORTS },
  retentionOtp: { label: "retention period for expired verification codes", value: process.env.NEXT_PUBLIC_LEGAL_RETENTION_OTP },
  lastUpdated: { label: "date these terms were last updated", value: process.env.NEXT_PUBLIC_LEGAL_LAST_UPDATED },
};

export type LegalKey = keyof typeof FIELDS;

/** Returns the configured value, or undefined when the owner has not provided it yet. */
export function legalValue(key: string): string | undefined {
  return FIELDS[key]?.value?.trim() || undefined;
}
export function legalLabel(key: string): string {
  return FIELDS[key]?.label ?? key;
}
export function legalKeys(): string[] {
  return Object.keys(FIELDS);
}
/** Keys still waiting for the owner; used by the internal readiness check and docs. */
export function missingLegalKeys(): string[] {
  return legalKeys().filter((key) => !legalValue(key));
}

export const LEGAL_PAGES = [
  { href: "/terms", label: "Terms & Conditions" },
  { href: "/privacy", label: "Privacy Policy" },
  { href: "/cookies", label: "Cookie Policy" },
  { href: "/data-protection", label: "Data Protection" },
  { href: "/copyright", label: "Copyright" },
  { href: "/contact", label: "Contact" },
] as const;
