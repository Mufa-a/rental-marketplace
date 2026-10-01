import type { Metadata } from "next";
import Link from "next/link";
import SiteHeader from "@/components/SiteHeader";
import SafetyTips from "@/components/SafetyTips";
import LegalText from "@/components/legal/LegalText";
import { LEGAL_STATUS } from "@/lib/legal/config";

export const revalidate = 86400;
export const metadata: Metadata = {
  title: "Contact",
  description: "How to contact Nyumbani, report a problem, or ask about your data.",
  alternates: { canonical: "/contact" },
  openGraph: { title: "Contact Nyumbani", description: "How to contact Nyumbani, report a problem, or ask about your data.", url: "/contact" },
};

export default function ContactPage() {
  return (
    <main className="shell legal-shell">
      <SiteHeader right={<Link className="navlink" href="/">Back to home</Link>} />
      <article className="glass legal-doc">
        {LEGAL_STATUS === "draft" && (
          <div className="legal-draft" role="note">
            <strong>Draft.</strong> Contact details below are waiting for the platform owner and are shown as <mark className="legal-placeholder">[TO BE PROVIDED]</mark> until then.
          </div>
        )}
        <p className="eyebrow">Help</p>
        <h1>Contact us</h1>
        <section className="legal-section">
          <h2>General, privacy and legal enquiries</h2>
          <ul>
            <li>Email: <LegalText text="{{contactEmail}}" /></li>
            <li>Phone: <LegalText text="{{contactPhone}}" /></li>
            <li>Address: <LegalText text="{{registeredAddress}}" /></li>
            <li>Data protection contact: <LegalText text="{{dpoContact}}" /></li>
          </ul>
          <p>Operated and developed under <LegalText text="{{operator}}" />.</p>
        </section>
        <section className="legal-section">
          <h2>Things you can do in the app</h2>
          <ul>
            <li><strong>Report a listing:</strong> open the listing and choose “Report this listing”.</li>
            <li><strong>Ask for your account to be deleted:</strong> sign in and open <Link href="/profile">Your profile</Link>.</li>
            <li><strong>Correct your details:</strong> update your name and email in <Link href="/profile">Your profile</Link>.</li>
          </ul>
        </section>
        <section className="legal-section">
          <h2>Staying safe</h2>
          <SafetyTips />
        </section>
      </article>
    </main>
  );
}
