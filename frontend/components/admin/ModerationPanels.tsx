"use client";

import Link from "next/link";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { date, dateTime, money, titleCase } from "@/lib/format";
import { Pager, useAdminList } from "./useAdminList";

type Notify = (text: string, error?: boolean) => void;

async function post(path: string, body: object, notify: Notify, success: string, reload: () => void) {
  try { await apiFetch(path, { method: "POST", body: JSON.stringify(body) }, true); notify(success); reload(); }
  catch (e) { notify(e instanceof Error ? e.message : "That action failed.", true); }
}

/** Prompt for a required note; returns null if the admin cancels. */
const ask = (question: string, required = true) => {
  const answer = window.prompt(question);
  if (answer === null || (required && !answer.trim())) return null;
  return answer.trim();
};

type ListingRow = {
  id: number; title: string; property: string; area: string; city: string; county: string; monthly_rent: number; bedrooms: number; unit_type: string;
  available: boolean; is_published: boolean; moderation_status: string; moderation_note: string; moderation_hold: boolean; verification_status: string;
  property_id: number; landlord: string; landlord_verified: boolean; possible_duplicate_of: number | null; open_reports: number; media_count: number; path: string; created_at: string;
};

export function ListingsPanel({ notify }: { notify: Notify }) {
  const list = useAdminList<ListingRow>("/admin/listings/", { moderation_status: "pending_review" });
  const act = (row: ListingRow, action: string, needsNote = false) => {
    const note = needsNote ? ask("Note for the landlord (required):") : "";
    if (note === null) return;
    void post(`/admin/listings/${row.id}/moderate/`, { action, note }, notify, `Listing ${titleCase(action).toLowerCase()} done.`, list.reload);
  };
  return <section className="admin-section">
    <div className="filters-row">
      <label>Status<select value={list.filters.moderation_status ?? ""} onChange={(e) => list.setFilter("moderation_status", e.target.value)}>
        <option value="pending_review">Awaiting review</option><option value="changes_requested">Changes requested</option><option value="rejected">Rejected</option><option value="approved">Approved</option><option value="">All</option></select></label>
      <label className="check"><input type="checkbox" checked={list.filters.reported === "true"} onChange={(e) => list.setFilter("reported", e.target.checked ? "true" : "")} />With open reports</label>
      <label className="check"><input type="checkbox" checked={list.filters.hold === "true"} onChange={(e) => list.setFilter("hold", e.target.checked ? "true" : "")} />On hold</label>
      <label>Search<input value={list.filters.q ?? ""} onChange={(e) => list.setFilter("q", e.target.value)} placeholder="Title, estate, phone" /></label>
    </div>
    {list.error && <p className="notice notice-error">{list.error}</p>}
    {list.data?.results.length === 0 && <div className="glass empty">Nothing in this queue.</div>}
    <div className="admin-cards">{list.data?.results.map((row) => <article className="glass activity-card" key={row.id}>
      <div className="activity-heading"><div>
        <span className="status">{titleCase(row.moderation_status)}</span>{row.moderation_hold && <span className="status status-danger">On hold</span>}
        {row.possible_duplicate_of && <span className="status status-warning">Possible duplicate of #{row.possible_duplicate_of}</span>}
        {row.open_reports > 0 && <span className="status status-danger">{row.open_reports} open report(s)</span>}
        <h3>#{row.id} {row.title}</h3>
        <p className="muted">{row.property} · {row.area}, {row.city}, {row.county} · {money(row.monthly_rent)} · {row.bedrooms} bd · {row.media_count} photos</p>
        <p className="muted small">Landlord {row.landlord}{row.landlord_verified ? " (ID-checked)" : ""} · property {titleCase(row.verification_status)} · listed {date(row.created_at)} · {row.available ? "available" : "occupied"} · {row.is_published ? "published" : "unpublished"}</p>
        {row.moderation_note && <p className="small">Note: {row.moderation_note}</p>}
      </div></div>
      <div className="inline-actions">
        {row.moderation_status !== "approved" && <button className="button-small" onClick={() => act(row, "approve")}>Approve</button>}
        <button className="button-secondary button-small" onClick={() => act(row, "request_changes", true)}>Request changes</button>
        <button className="button-secondary button-small" onClick={() => act(row, "reject", true)}>Reject</button>
        {row.moderation_hold ? <button className="button-secondary button-small" onClick={() => act(row, "unhide")}>Lift hold</button> : <button className="button-secondary button-small" onClick={() => act(row, "hide")}>Hold &amp; hide</button>}
        {row.available && <button className="button-secondary button-small" onClick={() => act(row, "mark_occupied")}>Mark occupied</button>}
        {row.is_published && row.moderation_status === "approved" && <Link className="navlink small" href={row.path} target="_blank">Open listing ↗</Link>}
      </div>
    </article>)}</div>
    <Pager page={list.page} data={list.data} setPage={list.setPage} />
  </section>;
}

type PropertyRow = { id: number; name: string; area: string; city: string; county: string; verification_status: string; units: number; landlord: string; fee_paid: boolean; updated_at: string };

export function PropertyVerificationPanel({ notify }: { notify: Notify }) {
  const list = useAdminList<PropertyRow>("/admin/properties/", { verification_status: "pending" });
  const decide = (row: PropertyRow, decision: string) => {
    const note = decision === "verified" ? "" : ask("Reason for the landlord (required):");
    if (note === null) return;
    void post(`/admin/properties/${row.id}/verification/`, { decision, note }, notify, "Decision saved.", list.reload);
  };
  return <section className="admin-section">
    <div className="filters-row"><label>Status<select value={list.filters.verification_status ?? ""} onChange={(e) => list.setFilter("verification_status", e.target.value)}>
      <option value="pending">Pending</option><option value="needs_review">Requires review</option><option value="verified">Verified</option><option value="rejected">Rejected</option><option value="">All</option></select></label></div>
    {list.data?.results.length === 0 && <div className="glass empty">No properties in this state.</div>}
    <div className="glass table-wrap"><table className="data-table"><thead><tr><th>Property</th><th>Units</th><th>Landlord</th><th>Fee</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>{list.data?.results.map((row) => <tr key={row.id}><td><strong>{row.name}</strong><br /><span className="muted small">{row.area}, {row.city}</span></td><td>{row.units}</td><td>{row.landlord}</td><td>{row.fee_paid ? "Paid" : "Not paid"}</td><td>{titleCase(row.verification_status)}</td>
        <td className="inline-actions"><button className="button-small" disabled={!row.fee_paid} title={row.fee_paid ? "" : "Verification requires the paid fee"} onClick={() => decide(row, "verified")}>Verify</button><button className="button-secondary button-small" onClick={() => decide(row, "needs_review")}>Needs review</button><button className="button-secondary button-small" onClick={() => decide(row, "rejected")}>Reject</button></td></tr>)}</tbody></table></div>
    <Pager page={list.page} data={list.data} setPage={list.setPage} />
  </section>;
}

type VerificationRow = { id: number; status: string; legal_name: string; id_type: string; id_last4: string; relationship: string; agency_name: string; submitted_at: string; landlord: string; documents_purged: boolean };
type VerificationDetail = VerificationRow & { landlord_phone: string; documents: { id: number; kind: string; label: string; content_type: string; size: number; available: boolean; reused_elsewhere: boolean }[]; properties: { id: number; name: string; area: string; city: string }[] };

export function LandlordVerificationPanel({ notify }: { notify: Notify }) {
  const list = useAdminList<VerificationRow>("/admin/landlord-verifications/", { status: "pending" });
  const [detail, setDetail] = useState<VerificationDetail | null>(null);
  const [preview, setPreview] = useState<{ url: string; type: string } | null>(null);

  async function open(id: number) {
    setPreview(null);
    try { setDetail(await apiFetch<VerificationDetail>(`/admin/landlord-verifications/${id}/`, {}, true)); }
    catch (e) { notify(e instanceof Error ? e.message : "Could not open.", true); }
  }
  async function view(docId: number) {
    // Fetched with the admin's token and shown from memory; never a shareable link.
    const access = localStorage.getItem("rental_access");
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
    const response = await fetch(`${base}/admin/verification-documents/${docId}/`, { headers: access ? { Authorization: `Bearer ${access}` } : {} });
    if (!response.ok) { notify("The document could not be opened (it may have been deleted after the retention period).", true); return; }
    const blob = await response.blob();
    setPreview({ url: URL.createObjectURL(blob), type: blob.type });
  }
  function decide(decision: string) {
    if (!detail) return;
    const note = decision === "verified" ? (ask("Optional note:", false) ?? "") : ask("What should the landlord fix? (required)");
    if (note === null) return;
    void post(`/admin/landlord-verifications/${detail.id}/decide/`, { decision, note }, notify, "Decision saved and the landlord notified.", () => { setDetail(null); void list.reload(); });
  }

  return <section className="admin-section">
    <div className="filters-row"><label>Status<select value={list.filters.status ?? ""} onChange={(e) => list.setFilter("status", e.target.value)}>
      <option value="pending">Pending</option><option value="needs_more_info">More info needed</option><option value="verified">Verified</option><option value="rejected">Rejected</option><option value="all">All</option></select></label></div>
    <p className="muted small">Documents are confidential. Open them only to make a decision; every view is recorded in the audit log.</p>
    <div className="split">
      <div>{list.data?.results.length === 0 && <div className="glass empty">No submissions here.</div>}
        {list.data?.results.map((row) => <button key={row.id} className={`glass list-pick${detail?.id === row.id ? " is-selected" : ""}`} onClick={() => void open(row.id)}>
          <strong>{row.legal_name}</strong><span className="muted small">{titleCase(row.relationship)} · {titleCase(row.id_type)} ••{row.id_last4} · {date(row.submitted_at)}</span></button>)}
        <Pager page={list.page} data={list.data} setPage={list.setPage} />
      </div>
      {detail && <article className="glass form-panel">
        <h3>{detail.legal_name}</h3>
        <p className="muted">{titleCase(detail.id_type)} ending {detail.id_last4} · {titleCase(detail.relationship)}{detail.agency_name ? ` (${detail.agency_name})` : ""} · {detail.landlord_phone}</p>
        <p className="small">Lists: {detail.properties.map((p) => `${p.name} (${p.area})`).join(", ") || "no properties yet"}</p>
        <ul className="plain-list">{detail.documents.map((d) => <li key={d.id} className="doc-row">{d.label} <span className="muted small">{Math.round(d.size / 1024)} KB</span>
          {d.reused_elsewhere && <span className="status status-danger">Same file used by another landlord</span>}
          {d.available ? <button className="button-secondary button-small" onClick={() => void view(d.id)}>View</button> : <span className="muted small">deleted</span>}</li>)}</ul>
        {preview && (preview.type === "application/pdf"
          ? <p><a className="button-secondary button-small" href={preview.url} download="verification-document.pdf">Open PDF</a> <span className="muted small">Delete the file after reviewing it.</span></p>
          : <img className="doc-preview" src={preview.url} alt="Verification document" />)}
        {detail.status === "pending" && <div className="inline-actions"><button onClick={() => decide("verified")}>Approve</button><button className="button-secondary" onClick={() => decide("needs_more_info")}>Ask for more</button><button className="button-danger" onClick={() => decide("rejected")}>Reject</button></div>}
      </article>}
    </div>
  </section>;
}

type ReportRow = { id: number; reason: string; detail: string; listing_id: number | null; listing: string | null; reported_user_id: number | null; reported_user: string | null; reporter: string; created_at: string; resolution: string; same_listing_open: number };

export function ReportsPanel({ notify }: { notify: Notify }) {
  const list = useAdminList<ReportRow>("/admin/reports/", { state: "open" });
  const resolve = (row: ReportRow, resolution: string, extra: object = {}) =>
    void post(`/admin/reports/${row.id}/resolve/`, { resolution, ...extra }, notify, "Report resolved.", list.reload);
  return <section className="admin-section">
    <div className="filters-row"><label>Show<select value={list.filters.state ?? ""} onChange={(e) => list.setFilter("state", e.target.value)}><option value="open">Open</option><option value="all">All</option></select></label></div>
    {list.data?.results.length === 0 && <div className="glass empty">No open reports.</div>}
    <div className="admin-cards">{list.data?.results.map((row) => <article className="glass activity-card" key={row.id}>
      <span className="status status-warning">{titleCase(row.reason)}</span>{row.same_listing_open > 1 && <span className="status status-danger">{row.same_listing_open} open on this listing</span>}
      <h3>{row.listing ?? "Account report"} {row.listing_id && <span className="muted">#{row.listing_id}</span>}</h3>
      <p>{row.detail || <span className="muted">No details given.</span>}</p>
      <p className="muted small">Reported {row.reported_user ?? "—"} · by {row.reporter} · {dateTime(row.created_at)}{row.resolution && ` · ${row.resolution}`}</p>
      {!row.resolution && <div className="inline-actions">
        <button className="button-secondary button-small" onClick={() => resolve(row, "dismissed")}>Dismiss</button>
        <button className="button-secondary button-small" onClick={() => resolve(row, "actioned", { hide_listing: true, all_for_listing: true })}>Hide listing</button>
        <button className="button-danger button-small" onClick={() => { const note = ask("Suspension reason (recorded):"); if (note) resolve(row, "actioned", { hide_listing: true, suspend_user: true, all_for_listing: true, note }); }}>Suspend landlord</button>
      </div>}
    </article>)}</div>
    <Pager page={list.page} data={list.data} setPage={list.setPage} />
  </section>;
}

type ReferralRow = { viewing_id: number; status: string; scheduled_at: string; unit: string; unit_id: number; unit_available: boolean; monthly_rent: number; tenant: string; landlord: string; tenant_report: string | null; landlord_report: string | null; flags: { reason: string; label: string; detail: string; created_at: string }[]; dispute_open: boolean };

export function ReferralPanel({ notify }: { notify: Notify }) {
  const list = useAdminList<ReferralRow>("/admin/referral-reviews/");
  const rule = (row: ReferralRow, rented: boolean) => {
    const note = ask(rented ? "Evidence that the home was rented (required, e.g. lease seen, both confirmed by phone):" : "Why no rental (required):");
    if (note === null) return;
    void post(`/admin/viewings/${row.viewing_id}/ruling/`, { rented, note }, notify, rented ? "Recorded as rented; the fee was created." : "Recorded as not rented.", list.reload);
  };
  return <section className="admin-section">
    <p className="muted">Viewings that may have become a tenancy without being reported, or where the two sides disagree. Contact both parties before ruling; rulings are audited and both sides are notified.</p>
    {list.data?.results.length === 0 && <div className="glass empty">Nothing to review.</div>}
    <div className="admin-cards">{list.data?.results.map((row) => <article className="glass activity-card" key={row.viewing_id}>
      <h3>{row.unit} <span className="muted">· viewing #{row.viewing_id}</span></h3>
      <p className="muted small">{dateTime(row.scheduled_at)} · rent {money(row.monthly_rent)} · unit {row.unit_available ? "still available" : "occupied"} · status {titleCase(row.status)}</p>
      <p>Tenant {row.tenant}: <strong>{row.tenant_report ? titleCase(row.tenant_report) : "no report"}</strong> · Landlord {row.landlord}: <strong>{row.landlord_report ? titleCase(row.landlord_report) : "no report"}</strong></p>
      <ul className="plain-list small">{row.flags.map((f) => <li key={f.reason}>⚑ {f.label}{f.detail ? ` — ${f.detail}` : ""}</li>)}{row.dispute_open && <li>⚑ Dispute open</li>}</ul>
      <div className="inline-actions"><button className="button-small" onClick={() => rule(row, true)}>It was rented — create fee</button><button className="button-secondary button-small" onClick={() => rule(row, false)}>Not rented</button></div>
    </article>)}</div>
    <Pager page={list.page} data={list.data} setPage={list.setPage} />
  </section>;
}
