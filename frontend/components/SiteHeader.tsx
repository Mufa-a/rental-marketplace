import Link from "next/link";
import type { ReactNode } from "react";
import AccountNav from "./AccountNav";

/**
 * One shared header. By default the right-hand side shows account-aware navigation;
 * pass `right` to replace it or `extra` to add page-specific links.
 */
export default function SiteHeader({ eyebrow, right, extra }: { eyebrow?: string; right?: ReactNode; extra?: ReactNode }) {
  return (
    <header className="site-header">
      <Link className="brand-mark" href="/">
        <span className="dot" aria-hidden="true" />
        Nyumbani
      </Link>
      <nav className="nav-actions" aria-label="Account">
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        {right ?? <AccountNav extra={extra} />}
      </nav>
    </header>
  );
}
