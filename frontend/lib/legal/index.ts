import { cookies } from "./cookies";
import { copyright } from "./copyright";
import { dataProtection } from "./dataProtection";
import { listingRules } from "./listingRules";
import { privacy } from "./privacy";
import { terms } from "./terms";
import { viewingPackages } from "./viewingPackages";

export const LEGAL_DOCS = { terms, privacy, cookies, "data-protection": dataProtection, copyright, "listing-rules": listingRules, "viewing-packages": viewingPackages } as const;
export type LegalSlug = keyof typeof LEGAL_DOCS;
export { LEGAL_VERSION, LEGAL_STATUS, LEGAL_PAGES } from "./config";
