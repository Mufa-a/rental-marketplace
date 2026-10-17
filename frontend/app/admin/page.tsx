"use client";

import { useEffect, useState } from "react";
import { apiFetch, signOut } from "@/lib/api";
import SiteHeader from "@/components/SiteHeader";

type FocusItem = {
  key: string; label: string; count: number; detail: string;
  severity: "high" | "medium" | "low"; action_label: string;
};
type AreaInsight = {
  city: string; area: string; active_listings: number; total_units: number;
  avg_rent_ksh: number | null; viewing_requests: number; demand_per_listing: number | null;
};
type ActivityItem = {
  action: string; label: string; object_type: string; object_id: string;
  actor: string; created_at: string;
};
type ReportRow = {
  id: number; reason: string; detail: string; listing: string | null; property: string | null; listing_hidden: boolean;
  open_reports_on_listing: number; reporter: string; reported_user: string | null; created_at: string;
};
type PendingProperty = {
  id: number; name: string; area: string; city: string; landlord: string; verification_status: string;
  verification_fee_paid: boolean; created_at: string;
};
type Page<T> = { count: number; results: T[] };
type Overview = {
  metrics: Record<string, number>;
  focus: FocusItem[];
  areas: AreaInsight[];
  recent_activity: ActivityItem[];
  viewing_requests: { id: number; status: string; unit: string; property: string; tenant: string; landlord: string; rent: number; created_at: string }[];
  viewings: { id: number; status: string; unit: string; property: string; scheduled_at: string; outcomes: { reporter: string; choice: string }[] }[];
  fees: { id: number; amount: number; status: string; unit: string; landlord: string; due_at: string | null; created_at: string }[];
  payments: { id: number; purpose: string; amount: number; status: string; phone_number: string; payer: string; created_at: string }[];
};

const money = (value: number) => `KSh ${value.toLocaleString()}`;
const label = (value: string) => value.replaceAll("_", " ").replace(/^./, (first) => first.toUpperCase());
const SEVERITY_LABEL: Record<FocusItem["severity"], string> = { high: "High priority", medium: "Medium priority", low: "Low priority" };

const TABS = ["reports", "properties", "requests", "viewings", "fees", "payments"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABEL: Record<Tab, string> = { reports: "Open reports", properties: "Pending verification", requests: "Viewing requests", viewings: "Viewings", fees: "Landlord fees", payments: "Payments" };
const FOCUS_TAB: Record<string, Tab> = {
  open_reports: "reports",
  pending_approvals: "properties",
  pending_viewing_requests: "requests",
  awaiting_outcome: "viewings",
  disputed_viewings: "viewings",
  overdue_fees: "fees",
};

export default function AdminDashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("reports");
  const [reports, setReports] = useState<Page<ReportRow>>({ count: 0, results: [] });
  const [pendingProperties, setPendingProperties] = useState<Page<PendingProperty>>({ count: 0, results: [] });

  useEffect(() => {
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    let role = "";
    try { role = JSON.parse(localStorage.getItem("rental_user") || "{}").role; } catch { localStorage.removeItem("rental_user"); }
    if (role !== "admin") { window.location.assign(role === "landlord" ? "/landlord" : "/tenant"); return; }
    apiFetch<Overview>("/admin/overview/", {}, true).then(setOverview)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load admin dashboard."))
      .finally(() => setLoading(false));
    apiFetch<Page<ReportRow>>("/admin/reports/?state=open", {}, true).then(setReports).catch(() => undefined);
    apiFetch<Page<PendingProperty>>("/admin/properties/?status=pending", {}, true).then(setPendingProperties).catch(() => undefined);
  }, []);

  const metrics = overview?.metrics;
  const cards = metrics ? ([
    ["Tenants", metrics.tenants, "sage"],
    ["Landlords", metrics.landlords, "sage"],
    ["Active listings", metrics.active_listings, "gold"],
    ["Pending approvals", metrics.pending_approvals, metrics.pending_approvals > 0 ? "danger" : "sage"],
    ["Viewing requests", metrics.viewing_requests, "gold"],
    ["Open reports", metrics.open_reports, metrics.open_reports > 0 ? "danger" : "sage"],
    ["Rentals reported", metrics.rentals_reported, "sage"],
    ["Fees due", metrics.fees_due, "gold"],
    ["Overdue fees", metrics.fees_overdue ?? 0, (metrics.fees_overdue ?? 0) > 0 ? "danger" : "sage"],
    ["Success fees collected", money(metrics.fees_collected_ksh), "sage"],
    ["Bundle revenue", money(metrics.bundle_revenue_ksh), "sage"],
    ["Failed payments", metrics.failed_payments, metrics.failed_payments > 0 ? "danger" : "sage"],
  ] as [string, number | string, string][]) : [];

  const maxDemand = overview ? Math.max(...overview.areas.map((a) => a.demand_per_listing ?? 0), 1) : 1;

  return (
    <main className="shell admin-shell">
      <SiteHeader eyebrow="Marketplace admin" right={<button className="button-secondary" onClick={signOut}>Sign out</button>} />
      <div className="page-head">
        <div>
          <p className="eyebrow">Operations</p>
          <h1>Marketplace overview</h1>
          <p className="muted">Live listings, viewing activity, trust reports, and payment status — nothing here is estimated.</p>
        </div>
      </div>

      {error && <div className="notice" role="alert">{error}</div>}
      {loading && <div className="glass empty">Loading marketplace activity…</div>}

      {metrics && overview && (
        <div className="admin-layout">
          <nav className="admin-sidenav" aria-label="Admin sections">
            <span className="side-link active">Dashboard</span>
            <div className="side-group">Jump to</div>
            <a href="#focus">Areas of focus</a>
            <a href="#areas">Area insights</a>
            <a href="#activity">Recent activity</a>
            <a href="#records">Reports &amp; payments</a>
          </nav>

          <div>
            <section className="admin-metrics">
              {cards.map(([title, value, accent]) => (
                <article className={`glass admin-metric accent-${accent}`} key={title}>
                  <span className="muted">{title}</span>
                  <strong>{value}</strong>
                </article>
              ))}
            </section>

            <section id="focus">
              <div className="section-lede"><h2>Areas of focus</h2><p className="muted">What needs attention today</p></div>
              {overview.focus.length === 0 ? (
                <div className="glass focus-empty">Nothing needs attention right now — the queue is clear.</div>
              ) : (
                <div className="focus-grid">
                  {overview.focus.map((item) => (
                    <article className="glass focus-card" data-severity={item.severity} key={item.key}>
                      <div className="focus-card-top">
                        <strong>{item.count}</strong>
                        <span className={`badge badge-${item.severity}`}>{SEVERITY_LABEL[item.severity]}</span>
                      </div>
                      <h3>{item.label}</h3>
                      <p>{item.detail}</p>
                      <a
                        className="focus-action"
                        href="#records"
                        onClick={() => { const target = FOCUS_TAB[item.key]; if (target) setTab(target); }}
                      >
                        {item.action_label} →
                      </a>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section id="areas">
              <div className="section-lede"><h2>Area insights</h2><p className="muted">Supply and demand by neighborhood</p></div>
              {overview.areas.length === 0 ? (
                <div className="glass empty">No published listings yet — area insights will appear once landlords publish units.</div>
              ) : (
                <div className="admin-table-wrap">
                  <table className="admin-table area-table">
                    <thead><tr><th>Area</th><th>Active listings</th><th>Avg. rent</th><th>Viewing requests</th><th>Demand</th></tr></thead>
                    <tbody>
                      {overview.areas.map((row) => {
                        const width = row.demand_per_listing ? Math.max(8, Math.round((row.demand_per_listing / maxDemand) * 60)) : 0;
                        return (
                          <tr key={`${row.city}-${row.area}`}>
                            <td className="area-name">{row.area}<span>{row.city}</span></td>
                            <td>{row.active_listings} of {row.total_units}</td>
                            <td>{row.avg_rent_ksh ? money(row.avg_rent_ksh) : "—"}</td>
                            <td>{row.viewing_requests}</td>
                            <td>{row.demand_per_listing !== null ? <><span className="demand-bar" style={{ width: `${width}px` }} />{row.demand_per_listing}/listing</> : "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section id="activity">
              <div className="section-lede"><h2>Recent activity</h2><p className="muted">Latest platform events</p></div>
              <div className="glass" style={{ padding: "4px 22px" }}>
                {overview.recent_activity.length === 0 ? (
                  <p className="muted empty">No activity recorded yet.</p>
                ) : (
                  <div className="activity-feed">
                    {overview.recent_activity.map((item, index) => (
                      <div className="activity-row" key={`${item.object_type}-${item.object_id}-${index}`}>
                        <span className="activity-dot" aria-hidden="true" />
                        <div>
                          <p>{item.label} <span className="muted">· {item.object_type} #{item.object_id}</span></p>
                          <time>{item.actor} · {new Date(item.created_at).toLocaleString()}</time>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <section id="records">
              <div className="section-lede"><h2>Reports &amp; payments</h2><p className="muted">Full activity records</p></div>
              <div className="tabbar" role="tablist">
                {TABS.map((t) => (
                  <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} type="button">{TAB_LABEL[t]}</button>
                ))}
              </div>

              {tab === "reports" && (
                <div className="admin-table-wrap">
                  <table className="admin-table"><thead><tr><th>Listing</th><th>Reason</th><th>Reporter</th><th>Open on listing</th><th>Reported</th></tr></thead>
                    <tbody>{reports.results.map((report) => <tr key={report.id}><td>{report.listing ?? "—"}{report.property ? <span className="muted"> · {report.property}</span> : null}{report.listing_hidden ? <span className="status status-paused"> hidden</span> : null}</td><td>{label(report.reason)}{report.detail ? <span className="muted"> — {report.detail}</span> : null}</td><td>{report.reporter}</td><td>{report.open_reports_on_listing}</td><td>{new Date(report.created_at).toLocaleDateString()}</td></tr>)}</tbody>
                  </table>
                  {reports.results.length === 0 && <p className="muted empty">No open reports. The queue is clear.</p>}
                  {reports.count > reports.results.length && <p className="muted">Showing the oldest {reports.results.length} of {reports.count} open reports.</p>}
                  <p className="muted">To dismiss, hide a listing or suspend a landlord, use <strong>Reports</strong> in the Django admin; each action is recorded against your account.</p>
                </div>
              )}
              {tab === "properties" && (
                <div className="admin-table-wrap">
                  <table className="admin-table"><thead><tr><th>Property</th><th>Area</th><th>Landlord</th><th>Fee paid</th><th>Submitted</th></tr></thead>
                    <tbody>{pendingProperties.results.map((property) => <tr key={property.id}><td>{property.name}</td><td>{property.area}, {property.city}</td><td>{property.landlord}</td><td>{property.verification_fee_paid ? "Yes" : "No"}</td><td>{new Date(property.created_at).toLocaleDateString()}</td></tr>)}</tbody>
                  </table>
                  {pendingProperties.results.length === 0 && <p className="muted empty">No properties are waiting for verification.</p>}
                  {pendingProperties.count > pendingProperties.results.length && <p className="muted">Showing the oldest {pendingProperties.results.length} of {pendingProperties.count} pending properties.</p>}
                  <p className="muted">To verify or reject, use <strong>Properties</strong> in the Django admin. Only properties with a successful verification payment can be marked verified.</p>
                </div>
              )}
              {tab === "requests" && (
                <div className="admin-table-wrap">
                  <table className="admin-table"><thead><tr><th>Property and unit</th><th>Tenant</th><th>Landlord</th><th>Monthly rent</th><th>Status</th><th>Requested</th></tr></thead>
                    <tbody>{overview.viewing_requests.map((item) => <tr key={item.id}><td>{item.property} · {item.unit}</td><td>{item.tenant}</td><td>{item.landlord}</td><td>{money(item.rent)}</td><td><span className="status">{label(item.status)}</span></td><td>{new Date(item.created_at).toLocaleDateString()}</td></tr>)}</tbody>
                  </table>
                  {overview.viewing_requests.length === 0 && <p className="muted empty">No requests yet.</p>}
                </div>
              )}
              {tab === "viewings" && (
                <div className="admin-table-wrap">
                  <table className="admin-table"><thead><tr><th>Property and unit</th><th>Scheduled</th><th>Status</th><th>Reports</th></tr></thead>
                    <tbody>{overview.viewings.map((viewing) => <tr key={viewing.id}><td>{viewing.property} · {viewing.unit}</td><td>{new Date(viewing.scheduled_at).toLocaleString()}</td><td>{label(viewing.status)}</td><td>{viewing.outcomes.map((result) => `${result.reporter}: ${label(result.choice)}`).join(" · ") || "Awaiting report"}</td></tr>)}</tbody>
                  </table>
                  {overview.viewings.length === 0 && <p className="muted empty">No viewings yet.</p>}
                </div>
              )}
              {tab === "fees" && (
                <div className="admin-table-wrap">
                  <table className="admin-table"><thead><tr><th>Unit</th><th>Landlord</th><th>Fee</th><th>Status</th><th>Due</th></tr></thead>
                    <tbody>{overview.fees.map((fee) => <tr key={fee.id}><td>{fee.unit}</td><td>{fee.landlord}</td><td>{money(fee.amount)}</td><td><span className={`status status-${fee.status}`}>{label(fee.status)}</span></td><td>{fee.due_at ? new Date(fee.due_at).toLocaleDateString() : "—"}</td></tr>)}</tbody>
                  </table>
                  {overview.fees.length === 0 && <p className="muted empty">No success fees yet.</p>}
                </div>
              )}
              {tab === "payments" && (
                <div className="admin-table-wrap">
                  <table className="admin-table"><thead><tr><th>Date</th><th>Type</th><th>Payer</th><th>Phone</th><th>Amount</th><th>Status</th></tr></thead>
                    <tbody>{overview.payments.map((payment) => <tr key={payment.id}><td>{new Date(payment.created_at).toLocaleString()}</td><td>{label(payment.purpose)}</td><td>{payment.payer}</td><td>{payment.phone_number}</td><td>{money(payment.amount)}</td><td><span className={`status status-${payment.status}`}>{label(payment.status)}</span></td></tr>)}</tbody>
                  </table>
                  {overview.payments.length === 0 && <p className="muted empty">No payments yet.</p>}
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </main>
  );
}
