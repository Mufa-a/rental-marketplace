import Link from "next/link";
import CurrentYear from "@/components/CurrentYear";
import { BRAND_NAME, LEGAL_PAGES, OPERATOR_NAME } from "@/lib/legal/config";

export default function SiteFooter() {
  return (
    <footer className="legal-footer" aria-label="Site footer">
      <div className="legal-footer-inner">
        <div>
          <strong className="legal-footer-brand">{BRAND_NAME}</strong>
          <p>Find a home, arrange a viewing, and agree the rest directly with the landlord.</p>
          <p className="legal-footer-copy">
            © <CurrentYear /> {OPERATOR_NAME}. All rights reserved. Listing content and photos belong to the people who upload them.
          </p>
        </div>
        <nav aria-label="Legal and help">
          {LEGAL_PAGES.map((page) => <Link key={page.href} href={page.href}>{page.label}</Link>)}
        </nav>
      </div>
    </footer>
  );
}
