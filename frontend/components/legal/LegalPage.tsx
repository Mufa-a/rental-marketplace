import Link from "next/link";
import SiteHeader from "@/components/SiteHeader";
import LegalText from "@/components/legal/LegalText";
import { LEGAL_PAGES, LEGAL_STATUS, LEGAL_VERSION, legalValue } from "@/lib/legal/config";
import type { LegalDoc } from "@/lib/legal/types";

/** One reusable renderer for every legal document, so wording lives in lib/legal/* and not in JSX. */
export default function LegalPage({ doc, showDates = true }: { doc: LegalDoc; showDates?: boolean }) {
  const updated = legalValue("lastUpdated");
  return (
    <main className="shell legal-shell">
      <SiteHeader right={<Link className="navlink" href="/">Back to home</Link>} />
      <article className="glass legal-doc">
        {LEGAL_STATUS === "draft" && (
          <div className="legal-draft" role="note">
            <strong>Draft for review.</strong> This document has not yet been reviewed by a qualified lawyer or privacy professional and is not final. Items marked <mark className="legal-placeholder">[TO BE PROVIDED]</mark> are waiting for the platform owner.
          </div>
        )}
        <p className="eyebrow">Legal</p>
        <h1>{doc.title}</h1>
        {showDates && (
          <p className="legal-meta">
            Last updated: {updated ?? <mark className="legal-placeholder">[DATE]</mark>} · Version {LEGAL_VERSION}
          </p>
        )}
        {doc.intro && <p className="legal-intro">{doc.intro}</p>}
        {doc.sections.length > 4 && (
          <nav className="legal-toc" aria-label={`${doc.title} contents`}>
            <strong>Contents</strong>
            <ol>
              {doc.sections.map((section) => (
                <li key={section.id}><a href={`#${section.id}`}>{section.heading.replace(/^\d+\.\s*/, "")}</a></li>
              ))}
            </ol>
          </nav>
        )}
        {doc.sections.map((section) => (
          <section id={section.id} key={section.id} className="legal-section">
            <h2>{section.heading}</h2>
            {section.body.map((block, index) => {
              if (typeof block === "string") return <p key={index}><LegalText text={block} /></p>;
              if ("sub" in block) return <h3 key={index}>{block.sub}</h3>;
              if ("list" in block) return <ul key={index}>{block.list.map((item, i) => <li key={i}><LegalText text={item} /></li>)}</ul>;
              return <p className="legal-note" key={index}><LegalText text={block.note} /></p>;
            })}
          </section>
        ))}
        <nav className="legal-related" aria-label="Other legal pages">
          {LEGAL_PAGES.map((page) => <Link key={page.href} href={page.href}>{page.label}</Link>)}
        </nav>
      </article>
    </main>
  );
}
