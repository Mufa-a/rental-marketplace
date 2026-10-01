/**
 * A paragraph, a sub-heading, a bullet list, or a highlighted note.
 * Tokens like double-brace key tokens are replaced from lib/legal/config.ts when rendered.
 */
export type Block = string | { sub: string } | { list: string[] } | { note: string };
export type Section = { id: string; heading: string; body: Block[] };
export type LegalDoc = {
  slug: string;
  title: string;
  description: string;
  intro?: string;
  sections: Section[];
};
