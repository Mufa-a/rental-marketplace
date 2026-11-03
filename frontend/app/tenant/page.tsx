"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { date, dateTime, money, titleCase } from "@/lib/format";
import { useRequireRole } from "@/lib/session";
import { ACTIVE, outcomeDue, requestStage } from "@/lib/status";
import type { Payment, ViewingRequest } from "@/lib/types";
import ContactCard from "@/components/ContactCard";
import PackagePicker from "@/components/PackagePicker";
import RequestTimeline from "@/components/RequestTimeline";
import SiteHeader from "@/components/SiteHeader";
import StatusBadge from "@/components/StatusBadge";

/** Matches the server rule: after the agreed time, a viewing is resolved by an outcome report, not a cancellation. */
const cancellable = (item: ViewingRequest) =>
  item.status === "pending_landlord" || (item.status === "approved" && item.viewing?.status === "scheduled" && new Date(item.viewing.scheduled_at).getTime() > Date.now());

const OUTCOMES: [string, string][] = [["rented", "I rented it"], ["did_not_rent", "I didn't rent it"], ["still_deciding", "Still deciding"]];

export default function TenantDashboard() {
  const user = useRequireRole("tenant");
  const [items, setItems] = useState<ViewingRequest[] | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [tab, setTab] = useState<"active" | "past" | "payments">("active");
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [cancelling, setCancelling] = useState<number | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    try {
      const [requests, history] = await Promise.all([
        apiFetch<ViewingRequest[]>("/viewings/requests/", {}, true),
        apiFetch<Payment[]>("/payments/mine/", {}, true),
      ]);
      setItems(requests); setPayments(history);
    } catch (error) { setMessage({ text: error instanceof Error ? error.message : "We could not load your activity.", error: true }); setItems([]); }
  }, []);
  useEffect(() => { if (user) void load(); }, [user, load]);

  async function act(path: string, body: object, success: string, id: number) {
    setBusyId(id); setMessage(null);
    try { await apiFetch(path, { method: "POST", body: JSON.stringify(body) }, true); setMessage({ text: success }); await load(); }
    catch (error) { setMessage({ text: error instanceof Error ? error.message : "That did not work. Please try again.", error: true }); }
    finally { setBusyId(null); }
  }

  if (!user) return <main className="shell"><div className="glass empty" aria-busy="true">Loading…</div></main>;
  const due = (items ?? []).filter(outcomeDue);
  // A rented report can still be added for a "did not rent" viewing within the attribution window (e.g. you decided later).
  const active = (items ?? []).filter((i) => ACTIVE.includes(i.status) && !["rented", "did_not_rent"].includes(i.viewing?.status ?? ""));
  const past = (items ?? []).filter((i) => !active.includes(i));
  const shown = tab === "active" ? active : past;

  return <main className="shell">
    <SiteHeader />
    <section className="dashboard-intro">
      <div><p className="eyebrow">Tenant dashboard</p><h1>Your viewings</h1><p className="muted">Requests, booked viewings and outcomes in one place.</p></div>
      <Link className="button" href="/">Find a home</Link>
    </section>

    {message && <p className={`notice ${message.error ? "notice-error" : "notice-success"}`} role="status" aria-live="polite">{message.text}</p>}

    {due.length > 0 && <section className="glass activity-card outcome-first" aria-labelledby="due-title">
      <p className="eyebrow">Action needed</p>
      <h2 id="due-title">How did your viewing go?</h2>
      <p className="muted">Your answer keeps listings accurate. If you rented the home, the listing is marked as let; if your answer and the landlord&apos;s differ, our team reviews it.</p>
      {due.map((item) => <div className="outcome-first-row" key={item.id}>
        <div><strong>{item.unit_title}</strong><p className="muted">{item.area} · viewed {dateTime(item.viewing!.scheduled_at)}</p></div>
        <div className="outcome-actions">{OUTCOMES.map(([choice, text]) =>
          <button key={choice} className={choice === "rented" ? "" : "button-secondary"} disabled={busyId === item.id}
                  onClick={() => void act(`/viewings/${item.viewing!.id}/outcome/`, { choice }, "Thank you. Your answer was recorded.", item.id)}>{text}</button>)}
        </div>
      </div>)}
    </section>}

    <div className="dashboard-columns">
      <section className="dashboard-content">
        <nav className="tabbar" role="tablist" aria-label="Activity">
          {([["active", `Active (${active.length})`], ["past", `History (${past.length})`], ["payments", "Payments"]] as const).map(([id, text]) =>
            <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{text}</button>)}
        </nav>

        {items === null && <div className="glass skeleton-card short" aria-busy="true" />}
        {items !== null && tab !== "payments" && shown.length === 0 && <div className="glass empty">
          <h3>{tab === "active" ? "No active requests" : "Nothing here yet"}</h3>
          <p>{tab === "active" ? "Find a home you like and request a viewing. The landlord's reply appears here." : "Finished, declined and cancelled requests appear here."}</p>
          {tab === "active" && <Link className="button" href="/">Browse homes</Link>}
        </div>}

        {tab !== "payments" && shown.map((item) => {
          const stage = requestStage(item);
          const viewing = item.viewing;
          const canReportLate = viewing?.status === "did_not_rent" && item.my_outcome !== "rented";
          return <article className="glass activity-card" key={item.id} id={`request-${item.id}`}>
            <div className="activity-heading">
              <div>
                <StatusBadge label={stage.label} tone={stage.tone} />
                <h3><Link href={item.unit_path}>{item.unit_title}</Link></h3>
                <p className="muted">{item.property_name} · {item.area} · {money(item.monthly_rent)}/month</p>
              </div>
              <time className="muted small" dateTime={item.created_at}>Requested {date(item.created_at)}</time>
            </div>
            <p className="next-step">{stage.next}</p>
            {viewing && item.status === "approved" && <p className="viewing-when"><strong>{dateTime(viewing.scheduled_at)}</strong>{viewing.reschedule_count > 0 && <span className="muted"> · moved {viewing.reschedule_count}×</span>}</p>}
            {ACTIVE.includes(item.status) && !item.unit_available && <p className="notice notice-warning">This home is no longer marked as available. Check with the landlord before you travel.</p>}
            {item.contact && <ContactCard contact={item.contact} who="landlord" />}
            {item.landlord_note && <p className="landlord-response"><strong>Landlord:</strong> {item.landlord_note}</p>}
            {item.cancel_reason && <p className="muted">Reason: {item.cancel_reason}</p>}
            {item.my_outcome && <p className="muted small">Your report: {titleCase(item.my_outcome)}</p>}
            <div className="inline-actions">
              {canReportLate && <button className="button-secondary button-small" disabled={busyId === item.id}
                onClick={() => void act(`/viewings/${viewing!.id}/outcome/`, { choice: "rented" }, "Thanks — we recorded that you rented this home.", item.id)}>I rented it after all</button>}
              {cancellable(item) && cancelling !== item.id &&
                <button className="button-secondary button-small" onClick={() => { setCancelling(item.id); setReason(""); }}>Cancel</button>}
            </div>
            {cancelling === item.id && <div className="inline-form">
              <p className="muted small">{item.status === "approved" ? "Cancelling an approved viewing uses your credit." : "Your credit will be returned."}</p>
              <label>Reason <span className="muted">(optional)</span><input value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} /></label>
              <div className="inline-actions">
                <button className="button-danger button-small" disabled={busyId === item.id} onClick={() => { setCancelling(null); void act(`/viewings/requests/${item.id}/cancel/`, { reason }, "Request cancelled.", item.id); }}>Confirm cancel</button>
                <button className="button-secondary button-small" onClick={() => setCancelling(null)}>Keep it</button>
              </div>
            </div>}
            <RequestTimeline requestId={item.id} />
          </article>;
        })}

        {tab === "payments" && (payments.length === 0
          ? <div className="glass empty"><h3>No payments yet</h3><p>Viewing package purchases appear here with their M-Pesa receipt.</p></div>
          : <div className="glass table-wrap"><table className="data-table">
              <thead><tr><th scope="col">Date</th><th scope="col">What</th><th scope="col">Amount</th><th scope="col">Status</th><th scope="col">Receipt</th></tr></thead>
              <tbody>{payments.map((p) => <tr key={p.id}><td>{date(p.created_at)}</td><td>{p.credits ? `${p.credits} viewing credits` : titleCase(p.purpose)}</td><td>{money(p.amount, p.currency)}</td><td>{titleCase(p.status)}</td><td>{p.provider_receipt ?? "—"}</td></tr>)}</tbody>
            </table></div>)}
      </section>
      <aside className="dashboard-side"><PackagePicker /></aside>
    </div>
  </main>;
}
