"use client";

import { useCallback, useEffect, useState } from "react";
import { useRequireRole } from "@/lib/session";
import SiteHeader from "@/components/SiteHeader";
import OverviewPanel from "@/components/admin/OverviewPanel";
import { LandlordVerificationPanel, ListingsPanel, PropertyVerificationPanel, ReferralPanel, ReportsPanel } from "@/components/admin/ModerationPanels";
import { AuditPanel, MarketPanel, PaymentsPanel, PricingPanel, UsersPanel } from "@/components/admin/BusinessPanels";

const SECTIONS = [
  ["overview", "Overview", "Operations"],
  ["listings", "Listing moderation", "Trust & safety"],
  ["reports", "Reports & complaints", "Trust & safety"],
  ["verifications", "Landlord verification", "Trust & safety"],
  ["properties", "Property verification", "Trust & safety"],
  ["referrals", "Referral reviews", "Revenue"],
  ["payments", "Payments", "Revenue"],
  ["pricing", "Packages & fees", "Revenue"],
  ["market", "Market reports", "Insights"],
  ["users", "Users", "Insights"],
  ["audit", "Audit log", "Insights"],
] as const;
type Section = (typeof SECTIONS)[number][0];

/** Admin console. The navigation is a convenience: every endpoint behind it is admin-only on the server. */
export default function AdminDashboard() {
  const user = useRequireRole("admin");
  const [section, setSection] = useState<Section>("overview");
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const notify = useCallback((text: string, error = false) => setMessage({ text, error }), []);

  useEffect(() => {
    const fromHash = window.location.hash.slice(1) as Section;
    if (SECTIONS.some(([id]) => id === fromHash)) setSection(fromHash);
  }, []);
  const go = (id: string) => { setSection(id as Section); setMessage(null); window.history.replaceState(null, "", `#${id}`); window.scrollTo({ top: 0 }); };

  if (!user) return <main className="shell"><div className="glass empty" aria-busy="true">Loading…</div></main>;
  const current = SECTIONS.find(([id]) => id === section)!;
  return <main className="shell admin-shell">
    <SiteHeader eyebrow="Admin" />
    <div className="admin-layout">
      <nav className="admin-sidenav" aria-label="Admin sections">
        {SECTIONS.map(([id, label, group], i) => <div key={id}>
          {(i === 0 || SECTIONS[i - 1][2] !== group) && <div className="side-group">{group}</div>}
          <button type="button" className={`side-link${section === id ? " active" : ""}`} aria-current={section === id ? "page" : undefined} onClick={() => go(id)}>{label}</button>
        </div>)}
      </nav>
      <div className="admin-main">
        <div className="page-head"><div><p className="eyebrow">{current[2]}</p><h1>{current[1]}</h1></div></div>
        {message && <p className={`notice ${message.error ? "notice-error" : "notice-success"}`} role="status" aria-live="polite">{message.text}</p>}
        {section === "overview" && <OverviewPanel onNavigate={go} />}
        {section === "listings" && <ListingsPanel notify={notify} />}
        {section === "reports" && <ReportsPanel notify={notify} />}
        {section === "verifications" && <LandlordVerificationPanel notify={notify} />}
        {section === "properties" && <PropertyVerificationPanel notify={notify} />}
        {section === "referrals" && <ReferralPanel notify={notify} />}
        {section === "payments" && <PaymentsPanel notify={notify} />}
        {section === "pricing" && <PricingPanel notify={notify} />}
        {section === "market" && <MarketPanel notify={notify} />}
        {section === "users" && <UsersPanel notify={notify} />}
        {section === "audit" && <AuditPanel notify={notify} />}
      </div>
    </div>
  </main>;
}
