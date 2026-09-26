"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, signOut } from "@/lib/api";

type Overview = {
  metrics: Record<string, number>;
  viewing_requests: { id: number; status: string; unit: string; property: string; tenant: string; landlord: string; rent: number; created_at: string }[];
  viewings: { id: number; status: string; unit: string; property: string; scheduled_at: string; outcomes: { reporter: string; choice: string }[] }[];
  fees: { id: number; amount: number; status: string; unit: string; landlord: string; due_at: string | null; created_at: string }[];
  payments: { id: number; purpose: string; amount: number; status: string; phone_number: string; payer: string; created_at: string }[];
};
const money = (value: number) => `KSh ${value.toLocaleString()}`;
const label = (value: string) => value.replaceAll("_", " ").replace(/^./, first => first.toUpperCase());

export default function AdminDashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    let role = "";
    try { role = JSON.parse(localStorage.getItem("rental_user") || "{}").role; } catch { localStorage.removeItem("rental_user"); }
    if (role !== "admin") { window.location.assign(role === "landlord" ? "/landlord" : "/tenant"); return; }
    apiFetch<Overview>("/admin/overview/", {}, true).then(setOverview)
      .catch(reason => setError(reason instanceof Error ? reason.message : "Could not load admin dashboard."))
      .finally(() => setLoading(false));
  }, []);
  const metrics = overview?.metrics;
  const cards = metrics ? [
    ["Tenants", metrics.tenants], ["Landlords", metrics.landlords], ["Active listings", metrics.active_listings],
    ["Viewing requests", metrics.viewing_requests], ["Reports due", metrics.pending_viewings],
    ["Rentals reported", metrics.rentals_reported], ["Fees due", metrics.fees_due],
    ["Success fees collected", money(metrics.fees_collected_ksh)], ["Bundle revenue", money(metrics.bundle_revenue_ksh)],
    ["Failed payments", metrics.failed_payments],
  ] as [string, number | string][] : [];
  return <main className="shell admin-shell"><header className="topnav"><Link href="/" className="brand">Nyumbani</Link><nav className="nav-actions"><span className="eyebrow">Marketplace admin</span><button className="button-secondary" onClick={signOut}>Sign out</button></nav></header>
    <section className="dashboard-intro"><p className="eyebrow">Separate admin dashboard</p><h1>Marketplace overview</h1><p className="muted">Track listings, viewing reports, landlord success fees, tenant bundles, and M-Pesa payment status.</p></section>
    {error && <div className="notice" role="alert">{error}</div>}{loading && <div className="glass empty">Loading marketplace activity…</div>}
    {metrics && <><section className="admin-metrics">{cards.map(([title, value]) => <article className="glass admin-metric" key={title}><span className="muted">{title}</span><strong>{value}</strong></article>)}</section>
      <section className="dashboard-content"><h2>Landlord success fees</h2><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Unit</th><th>Landlord</th><th>Fee</th><th>Status</th><th>Due</th></tr></thead><tbody>{overview.fees.map(fee => <tr key={fee.id}><td>{fee.unit}</td><td>{fee.landlord}</td><td>{money(fee.amount)}</td><td><span className={`status status-${fee.status}`}>{label(fee.status)}</span></td><td>{fee.due_at ? new Date(fee.due_at).toLocaleDateString() : "—"}</td></tr>)}</tbody></table>{overview.fees.length === 0 && <p className="muted">No success fees yet.</p>}</div></section>
      <section className="dashboard-content"><h2>Payments</h2><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Date</th><th>Type</th><th>Payer</th><th>Phone</th><th>Amount</th><th>Status</th></tr></thead><tbody>{overview.payments.map(payment => <tr key={payment.id}><td>{new Date(payment.created_at).toLocaleString()}</td><td>{label(payment.purpose)}</td><td>{payment.payer}</td><td>{payment.phone_number}</td><td>{money(payment.amount)}</td><td><span className={`status status-${payment.status}`}>{label(payment.status)}</span></td></tr>)}</tbody></table>{overview.payments.length === 0 && <p className="muted">No payments yet.</p>}</div></section>
      <section className="dashboard-content"><h2>Viewing outcomes</h2><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Property and unit</th><th>Scheduled</th><th>Status</th><th>Reports</th></tr></thead><tbody>{overview.viewings.map(viewing => <tr key={viewing.id}><td>{viewing.property} · {viewing.unit}</td><td>{new Date(viewing.scheduled_at).toLocaleString()}</td><td>{label(viewing.status)}</td><td>{viewing.outcomes.map(result => `${result.reporter}: ${label(result.choice)}`).join(" · ") || "Awaiting report"}</td></tr>)}</tbody></table>{overview.viewings.length === 0 && <p className="muted">No viewings yet.</p>}</div></section>
      <section className="dashboard-content"><h2>Recent viewing requests</h2><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Property and unit</th><th>Tenant</th><th>Landlord</th><th>Monthly rent</th><th>Status</th><th>Requested</th></tr></thead><tbody>{overview.viewing_requests.map(item => <tr key={item.id}><td>{item.property} · {item.unit}</td><td>{item.tenant}</td><td>{item.landlord}</td><td>{money(item.rent)}</td><td>{label(item.status)}</td><td>{new Date(item.created_at).toLocaleDateString()}</td></tr>)}</tbody></table>{overview.viewing_requests.length === 0 && <p className="muted">No requests yet.</p>}</div></section></>}
  </main>;
}
