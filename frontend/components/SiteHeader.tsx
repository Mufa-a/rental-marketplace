import Link from "next/link";
import type { ReactNode } from "react";

/**
 * One shared header instead of every page hand-rolling its own <header
 * className="topnav">. Keeps the brand mark, spacing, and link styling
 * identical everywhere it's used.
 */
export default function SiteHeader({ eyebrow, right }: { eyebrow?: string; right: ReactNode }) {
  return (
    <header className="site-header">
      <Link className="brand-mark" href="/">
        <span className="dot" aria-hidden="true" />
        Nyumbani
      </Link>
      <nav className="nav-actions">
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        {right}
      </nav>
    </header>
  );
}
