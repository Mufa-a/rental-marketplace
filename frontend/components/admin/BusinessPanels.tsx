"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, downloadFile } from "@/lib/api";
import { date, dateTime, money, titleCase } from "@/lib/format";
import { Pager, useAdminList } from "./useAdminList";

type Notify = (text: string, error?: boolean) => void;
const today = () => new Date().toISOString().slice(0, 10);

function ExportButton({ name, query = "", notify, label = "Export CSV" }: { name: string; query?: string; notify: Notify; label?: string }) {
  return <button className="button-secondary button-small" onClick={() => downloadFile(`/admin/exports/${name}.csv${query ? `?${query}` : ""}`, `${name}-${today()}.csv`).catch((e) => notify(e.message, true))}>{label}</button>;
}

type PaymentRow = { id: number; purpose: string; status: string; amount: number; currency: string; credits: number | null; phone: string; provider: string; provider_reference: string; receipt: string | null; failure_reason: string; created_at: string; completed_at: string | null; refunded_at: string | null; refund_reason: string };

export function PaymentsPanel({ notify }: { notify: Notify }) {
  const list = useAdminList<PaymentRow>("/admin/payments/");
  async function act(row: PaymentRow, action: "refund" | "reconcile") {
    let body = {};
    if (action === "refund") {
      const reason = window.prompt("Refunds are sent through M-Pesa (reversal/B2C) first. Record how and why it was refunded, e.g. the reversal reference:");
      if (!reason?.trim()) return;
      body = { reason };
    }
    try { await apiFetch(`/admin/payments/${row.id}/${action}/`, { method: "POST", body: JSON.stringify(body) }, true); notify(action === "refund" ? "Refund recorded and access reversed." : "Checked with M-Pesa."); void list.reload(); }
    catch (e) { notify(e instanceof Error ? e.message : "Action failed.", true); }
  }
  const query = new URLSearchParams(Object.entries(list.filters).filter(([, v]) => v)).toString();
  return <section className="admin-section">
    <div className="filters-row">
      <label>Status<select value={list.filters.status ?? ""} onChange={(e) => list.setFilter("status", e.target.value)}><option value="">All</option>{["pending", "successful", "failed", "cancelled", "refunded", "disputed"].map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}</select></label>
      <label>Type<select value={list.filters.purpose ?? ""} onChange={(e) => list.setFilter("purpose", e.target.value)}><option value="">All</option><option value="viewing_credits">Viewing packages</option><option value="referral_fee">Success fees</option><option value="verification_fee">Verification fees</option></select></label>
      <label>Since<input type="date" value={list.filters.since ?? ""} onChange={(e) => list.setFilter("since", e.target.value)} /></label>
      <label>Receipt / phone<input value={list.filters.q ?? ""} onChange={(e) => list.setFilter("q", e.target.value)} /></label>
      <ExportButton name="payments" query={query} notify={notify} />
    </div>
    {list.data?.totals && <div className="admin-metrics compact">{Object.entries(list.data.totals).map(([status, t]) => <article className="glass admin-metric" key={status}><span className="muted">{titleCase(status)}</span><strong>{money(t.amount)}</strong><span className="muted small">{t.count} payments</span></article>)}</div>}
    <div className="glass table-wrap"><table className="data-table"><thead><tr><th>Date</th><th>Type</th><th>Amount</th><th>Status</th><th>Receipt</th><th>Phone</th><th></th></tr></thead>
      <tbody>{list.data?.results.map((p) => <tr key={p.id}>
        <td>{dateTime(p.created_at)}</td><td>{titleCase(p.purpose)}{p.credits ? ` (${p.credits})` : ""}</td><td>{money(p.amount, p.currency)}</td>
        <td><span className={`status status-${p.status}`}>{titleCase(p.status)}</span>{p.failure_reason && <span className="muted small"> {p.failure_reason}</span>}{p.refund_reason && <span className="muted small"> {p.refund_reason}</span>}</td>
        <td>{p.receipt ?? "—"}</td><td>{p.phone}</td>
        <td className="inline-actions">{p.status === "pending" && <button className="button-secondary button-small" onClick={() => void act(p, "reconcile")}>Check status</button>}
          {["successful", "disputed"].includes(p.status) && <button className="button-secondary button-small" onClick={() => void act(p, "refund")}>Record refund</button>}</td>
      </tr>)}</tbody></table></div>
    <Pager page={list.page} data={list.data} setPage={list.setPage} />
  </section>;
}

type PackageRow = { id: number; country: string; name: string; description: string; credits: number; price: number; currency: string; is_active: boolean; sort_order: number };
type FeeRow = { id: number; country: string; min_rent: number; max_rent: number | null; fee_type: string; amount: number; percent: string; currency: string; is_active: boolean };
type PriceRow = { id: number; country: string; code: string; amount: number; currency: string; is_active: boolean };

export function PricingPanel({ notify }: { notify: Notify }) {
  const [packages, setPackages] = useState<PackageRow[]>([]);
  const [rules, setRules] = useState<FeeRow[]>([]);
  const [prices, setPrices] = useState<PriceRow[]>([]);
  const load = useCallback(async () => {
    const [p, r, s] = await Promise.all([apiFetch<PackageRow[]>("/admin/pricing/packages/", {}, true), apiFetch<FeeRow[]>("/admin/pricing/fee-rules/", {}, true), apiFetch<PriceRow[]>("/admin/pricing/service-prices/", {}, true)]);
    setPackages(p); setRules(r); setPrices(s);
  }, []);
  useEffect(() => { void load().catch((e) => notify(e.message, true)); }, [load, notify]);

  async function save(path: string, body: object, method = "PATCH") {
    try { await apiFetch(path, { method, body: JSON.stringify(body) }, true); notify("Saved. New prices apply to new purchases immediately; past payments keep their original amounts."); void load(); }
    catch (e) { notify(e instanceof Error ? e.message : "Could not save.", true); }
  }
  const edit = (label: string, current: string | number | null) => { const v = window.prompt(label, current == null ? "" : String(current)); return v === null ? null : v.trim(); };

  return <section className="admin-section">
    <div className="glass form-panel">
      <div className="section-heading"><h2>Viewing packages</h2><button className="button-small" onClick={() => {
        const credits = edit("Number of viewing credits:", 3); const price = credits && edit("Price (KES):", 120); const name = price && edit("Name:", `${credits} viewings`);
        if (name) void save("/admin/pricing/packages/", { country: "KE", name, credits: Number(credits), price: Number(price) }, "POST");
      }}>Add package</button></div>
      <table className="data-table"><thead><tr><th>Country</th><th>Name</th><th>Credits</th><th>Price</th><th>Per viewing</th><th>Active</th><th></th></tr></thead>
        <tbody>{packages.map((p) => <tr key={p.id} className={p.is_active ? "" : "is-muted"}><td>{p.country}</td><td>{p.name}</td><td>{p.credits}</td><td>{money(p.price, p.currency)}</td><td>{money(p.price / p.credits, p.currency)}</td><td>{p.is_active ? "Yes" : "No"}</td>
          <td className="inline-actions"><button className="button-secondary button-small" onClick={() => { const v = edit(`New price for ${p.name}:`, p.price); if (v) void save(`/admin/pricing/packages/${p.id}/`, { price: Number(v) }); }}>Change price</button>
            <button className="button-secondary button-small" onClick={() => void save(`/admin/pricing/packages/${p.id}/`, { is_active: !p.is_active })}>{p.is_active ? "Retire" : "Reactivate"}</button></td></tr>)}</tbody></table>
    </div>
    <div className="glass form-panel">
      <div className="section-heading"><h2>Landlord success-fee rules</h2><button className="button-small" onClick={() => {
        const min = edit("Minimum monthly rent:", 0); const max = min !== null ? edit("Maximum monthly rent (blank = no limit):", "") : null; const amount = max !== null ? edit("Fixed fee (KES):", 2000) : null;
        if (amount) void save("/admin/pricing/fee-rules/", { country: "KE", min_rent: Number(min), max_rent: max ? Number(max) : null, fee_type: "fixed", amount: Number(amount) }, "POST");
      }}>Add rule</button></div>
      <p className="muted small">The active rule matching the agreed rent applies when a rental is confirmed. Make sure active bands do not overlap or leave gaps.</p>
      <table className="data-table"><thead><tr><th>Country</th><th>Rent from</th><th>Rent to</th><th>Fee</th><th>Active</th><th></th></tr></thead>
        <tbody>{rules.map((r) => <tr key={r.id} className={r.is_active ? "" : "is-muted"}><td>{r.country}</td><td>{money(r.min_rent)}</td><td>{r.max_rent == null ? "no limit" : money(r.max_rent)}</td><td>{r.fee_type === "percent" ? `${r.percent}% of rent` : money(r.amount, r.currency)}</td><td>{r.is_active ? "Yes" : "No"}</td>
          <td className="inline-actions"><button className="button-secondary button-small" onClick={() => { const v = edit("New fixed fee (KES):", r.amount); if (v) void save(`/admin/pricing/fee-rules/${r.id}/`, { fee_type: "fixed", amount: Number(v) }); }}>Change fee</button>
            <button className="button-secondary button-small" onClick={() => void save(`/admin/pricing/fee-rules/${r.id}/`, { is_active: !r.is_active })}>{r.is_active ? "Deactivate" : "Activate"}</button></td></tr>)}</tbody></table>
    </div>
    <div className="glass form-panel">
      <h2>Optional landlord services</h2>
      <table className="data-table"><thead><tr><th>Country</th><th>Service</th><th>Price</th><th>Active</th><th></th></tr></thead>
        <tbody>{prices.map((s) => <tr key={s.id}><td>{s.country}</td><td>{titleCase(s.code)}</td><td>{money(s.amount, s.currency)}</td><td>{s.is_active ? "Yes" : "No"}</td>
          <td className="inline-actions"><button className="button-secondary button-small" onClick={() => { const v = edit("New price (KES):", s.amount); if (v) void save(`/admin/pricing/service-prices/${s.id}/`, { amount: Number(v) }); }}>Change price</button></td></tr>)}</tbody></table>
    </div>
  </section>;
}

type AreaRow = { county: string; town?: string; estate?: string; active_listings: number; total_units: number; occupied_units: number; avg_rent: number | null; listing_views: number; viewing_requests: number; tenants_searching: number; completed_viewings: number; rentals: number; demand_per_listing: number; undersupplied: boolean };
type Trends = { dates: string[]; series: Record<string, number[]> };

function Sparkline({ values, label }: { values: number[]; label: string }) {
  const max = Math.max(...values, 1);
  const points = values.map((v, i) => `${(i / Math.max(values.length - 1, 1)) * 100},${30 - (v / max) * 28}`).join(" ");
  const total = values.reduce((a, b) => a + b, 0);
  return <figure className="glass spark"><figcaption><span className="muted small">{label}</span><strong>{label === "Revenue" ? money(total) : total}</strong></figcaption>
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" role="img" aria-label={`${label}: ${total} over the period`}><polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" /></svg></figure>;
}

export function MarketPanel({ notify }: { notify: Notify }) {
  const [group, setGroup] = useState("estate");
  const [days, setDays] = useState("90");
  const [rows, setRows] = useState<AreaRow[] | null>(null);
  const [trends, setTrends] = useState<Trends | null>(null);
  useEffect(() => {
    apiFetch<{ rows: AreaRow[] }>(`/admin/market/areas/?group=${group}&days=${days}`, {}, true).then((d) => setRows(d.rows)).catch((e) => notify(e.message, true));
  }, [group, days, notify]);
  useEffect(() => { apiFetch<Trends>("/admin/market/trends/?days=30", {}, true).then(setTrends).catch(() => undefined); }, []);
  return <section className="admin-section">
    {trends && <div className="spark-row">{([["viewing_requests", "Viewing requests"], ["approved", "Approved"], ["rentals", "Rentals"], ["signups", "Sign-ups"], ["revenue", "Revenue"]] as const).map(([key, label]) => <Sparkline key={key} values={trends.series[key]} label={label} />)}</div>}
    <div className="filters-row">
      <label>Group by<select value={group} onChange={(e) => setGroup(e.target.value)}><option value="county">County</option><option value="town">Town</option><option value="estate">Estate</option></select></label>
      <label>Demand window<select value={days} onChange={(e) => setDays(e.target.value)}><option value="30">30 days</option><option value="90">90 days</option><option value="180">180 days</option><option value="365">1 year</option></select></label>
      <ExportButton name="areas" query={`group=${group}&days=${days}`} notify={notify} label="Export this report" />
      <ExportButton name="listings" notify={notify} label="Export listings" />
      <ExportButton name="viewings" notify={notify} label="Export viewings" />
    </div>
    <p className="muted small">&ldquo;Undersupplied&rdquo; = at least 3 viewing requests and 3+ requests per active listing — places worth recruiting landlords.</p>
    <div className="glass table-wrap"><table className="data-table"><thead><tr><th>Place</th><th>Active listings</th><th>Occupied</th><th>Avg rent</th><th>Views</th><th>Requests</th><th>Tenants</th><th>Rentals</th><th>Demand / listing</th></tr></thead>
      <tbody>{rows?.map((r, i) => <tr key={i} className={r.undersupplied ? "is-highlight" : ""}><td><strong>{r.estate ?? r.town ?? r.county}</strong><br /><span className="muted small">{Array.from(new Set([r.town, r.county])).filter((x) => x && x !== (r.estate ?? r.town ?? r.county)).join(", ")}</span>{r.undersupplied && <span className="status status-warning">Undersupplied</span>}</td>
        <td>{r.active_listings}</td><td>{r.occupied_units}</td><td>{r.avg_rent ? money(r.avg_rent) : "—"}</td><td>{r.listing_views}</td><td>{r.viewing_requests}</td><td>{r.tenants_searching}</td><td>{r.rentals}</td><td>{r.demand_per_listing}</td></tr>)}</tbody></table>
      {rows?.length === 0 && <p className="muted empty">No data for this period yet.</p>}</div>
  </section>;
}

type UserRow = { id: number; role: string; phone: string; verified: boolean; active: boolean; joined: string };
type UserDetail = { id: number; role: string; phone: string; name: string; email: string; active: boolean; joined: string; restrictions: { reason: string; created_at: string }[]; listings?: number; viewing_requests?: number; payments?: number; reports_received: number; landlord_verified?: boolean };

export function UsersPanel({ notify }: { notify: Notify }) {
  const list = useAdminList<UserRow>("/admin/users/");
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const open = (id: number) => apiFetch<UserDetail>(`/admin/users/${id}/`, {}, true).then(setDetail).catch((e) => notify(e.message, true));
  async function act(action: "suspend" | "reinstate") {
    if (!detail) return;
    const reason = action === "suspend" ? window.prompt("Reason for suspension (recorded and kept):") : "";
    if (action === "suspend" && !reason?.trim()) return;
    try { await apiFetch(`/admin/users/${detail.id}/${action}/`, { method: "POST", body: JSON.stringify({ reason }) }, true); notify(action === "suspend" ? "Account suspended and listings hidden." : "Account reinstated."); void open(detail.id); void list.reload(); }
    catch (e) { notify(e instanceof Error ? e.message : "Failed.", true); }
  }
  return <section className="admin-section">
    <div className="filters-row">
      <label>Role<select value={list.filters.role ?? ""} onChange={(e) => list.setFilter("role", e.target.value)}><option value="">All</option><option value="tenant">Tenants</option><option value="landlord">Landlords</option><option value="admin">Admins</option></select></label>
      <label>Search<input value={list.filters.search ?? ""} onChange={(e) => list.setFilter("search", e.target.value)} placeholder="Phone or name" /></label>
    </div>
    <div className="split">
      <div className="glass table-wrap"><table className="data-table"><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Joined</th></tr></thead>
        <tbody>{list.data?.results.map((u) => <tr key={u.id} className="clickable" onClick={() => void open(u.id)}><td><button className="linklike">{u.phone}</button></td><td>{titleCase(u.role)}</td><td>{u.active ? (u.verified ? "Active" : "Unverified") : "Suspended / inactive"}</td><td>{date(u.joined)}</td></tr>)}</tbody></table>
        <Pager page={list.page} data={list.data} setPage={list.setPage} /></div>
      {detail && <article className="glass form-panel">
        <h3>{detail.name || detail.phone}</h3>
        <p className="muted">{titleCase(detail.role)} · {detail.phone}{detail.email ? ` · ${detail.email}` : ""} · joined {date(detail.joined)}</p>
        <ul className="plain-list small">
          {detail.listings != null && <li>{detail.listings} listings · {detail.landlord_verified ? "ID-checked" : "not ID-checked"}</li>}
          {detail.viewing_requests != null && <li>{detail.viewing_requests} viewing requests · {detail.payments} successful payments</li>}
          <li>{detail.reports_received} reports received</li>
          {detail.restrictions.map((r, i) => <li key={i}>Restriction: {r.reason} ({date(r.created_at)})</li>)}
        </ul>
        {detail.role !== "admin" && (detail.active ? <button className="button-danger button-small" onClick={() => void act("suspend")}>Suspend account</button> : <button className="button-small" onClick={() => void act("reinstate")}>Reinstate</button>)}
        <p className="muted small">Opening this record was logged.</p>
      </article>}
    </div>
  </section>;
}

type AuditRow = { id: number; action: string; object_type: string; object_id: string; actor: string; metadata: Record<string, unknown>; created_at: string; entry_hash: string };

export function AuditPanel({ notify }: { notify: Notify }) {
  const list = useAdminList<AuditRow>("/admin/audit-logs/");
  const [chain, setChain] = useState<string>("");
  async function verify() {
    try { const r = await apiFetch<{ intact: boolean; checked: number; first_broken_id: number | null }>("/admin/audit-logs/verify/", {}, true); setChain(r.intact ? `Chain intact — ${r.checked} entries verified.` : `Chain BROKEN at entry ${r.first_broken_id}. Investigate immediately.`); }
    catch (e) { notify(e instanceof Error ? e.message : "Verification failed.", true); }
  }
  return <section className="admin-section">
    <div className="filters-row">
      <label>Action starts with<input value={list.filters.action ?? ""} onChange={(e) => list.setFilter("action", e.target.value)} placeholder="payment., viewing., unit.moderation" /></label>
      <label>Object type<input value={list.filters.object_type ?? ""} onChange={(e) => list.setFilter("object_type", e.target.value)} placeholder="payments.Payment" /></label>
      <label>Object id<input value={list.filters.object_id ?? ""} onChange={(e) => list.setFilter("object_id", e.target.value)} /></label>
      <button className="button-secondary button-small" onClick={() => void verify()}>Verify tamper-evident chain</button>
    </div>
    {chain && <p className={`notice ${chain.includes("BROKEN") ? "notice-error" : "notice-success"}`}>{chain}</p>}
    <div className="glass table-wrap"><table className="data-table"><thead><tr><th>#</th><th>When</th><th>Action</th><th>Object</th><th>Actor</th><th>Details</th></tr></thead>
      <tbody>{list.data?.results.map((e) => <tr key={e.id}><td>{e.id}</td><td>{dateTime(e.created_at)}</td><td><code>{e.action}</code></td><td>{e.object_type} {e.object_id}</td><td>{e.actor}</td><td className="small"><code>{Object.keys(e.metadata).length ? JSON.stringify(e.metadata).slice(0, 140) : ""}</code></td></tr>)}</tbody></table></div>
    <Pager page={list.page} data={list.data} setPage={list.setPage} />
  </section>;
}
