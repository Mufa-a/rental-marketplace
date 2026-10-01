import { cookies } from "./cookies";
import { copyright } from "./copyright";
import { dataProtection } from "./dataProtection";
import { privacy } from "./privacy";
import { terms } from "./terms";

export const LEGAL_DOCS = { terms, privacy, cookies, "data-protection": dataProtection, copyright } as const;
export type LegalSlug = keyof typeof LEGAL_DOCS;
export { LEGAL_VERSION, LEGAL_STATUS, LEGAL_PAGES } from "./config";
