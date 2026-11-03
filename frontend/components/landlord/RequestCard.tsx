"use client";

import Link from "next/link";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { date, dateTime, money, titleCase } from "@/lib/format";
import { outcomeDue, requestStage } from "@/lib/status";
import type { ViewingRequest } from "@/lib/types";
import ContactCard from "../ContactCard";
import RequestTimeline from "../RequestTimeline";
import StatusBadge from "../StatusBadge";

const localInput = (d: Date) => { const copy = new Date(d); copy.setMinutes(copy.getMinutes() - copy.getTimezoneOffset()); return copy.toISOString().slice(0, 16); };
const tomorrowTen = () => { const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(10, 0, 0, 0); return localInput(d); };
const OUTCOMES: [string, string][] = [["rented", "Rented to this tenant"], ["did_not_rent", "Did not rent"], ["still_deciding", "Still deciding"], ["no_show", "Tenant did not show up"]];

export default function RequestCard({ item, onChanged }: { item: ViewingRequest; onChanged: (message: string, error?: boolean) => void }) {
  const [when, setWhen] = useState(item.viewing ? localInput(new Date(item.viewing.scheduled_at)) : tomorrowTen());
  const [note, setNote] = useState("");
  const [mode, setMode] = useState<"" | "decline" | "reschedule" | "cancel">("");
  const [busy, setBusy] = useState(false);
  const stage = requestStage(item);
  const viewing = item.viewing;
  const upcoming = viewing?.status === "scheduled" && new Date(viewing.scheduled_at).getTime() > Date.now();

  async function post(path: string, body: object, success: string) {
    setBusy(true);
    try {
      const result = await apiFetch<{ payment_status?: string; fee?: { amount: number; currency: string } }>(path, { method: "POST", body: JSON.stringify(body) }, true);
      setMode("");
      onChanged(result?.fee ? `Rental recorded and the home was taken off the market. A ${money(result.fee.amount, result.fee.currency)} success fee is due — ${result.payment_status === "pending" ? "check your phone for the M-Pesa prompt" : "pay it from the Payments tab"}.` : success);
    } catch (error) { onChanged(error instanceof Error ? error.message : "That did not work. Please try again.", true); }
    finally { setBusy(false); }
  }

  const iso = (value: string) => new Date(value).toISOString();
  return <article className="glass activity-card" id={`request-${item.id}`}>
    <div className="activity-heading">
      <div>
        <StatusBadge label={stage.label} tone={stage.tone} />
        <h3><Link href={item.unit_path}>{item.unit_title}</Link></h3>
        <p className="muted">{item.property_name} · {item.area} · {money(item.monthly_rent)}/month</p>
      </div>
      <time className="muted small" dateTime={item.created_at}>{date(item.created_at)}</time>
    </div>
    <p className="next-step">{stage.next}</p>
    <div className="request-message">
      <span className="eyebrow">Tenant&apos;s message</span>
      <p>{item.note || "No message."}</p>
      {item.preferred_times.length > 0 && <p className="muted small">Prefers: {item.preferred_times.join(", ")}</p>}
    </div>

    {item.status === "pending_landlord" && <div className="request-schedule">
      <label>Viewing date and time<input type="datetime-local" min={localInput(new Date(Date.now() + 30 * 60000))} value={when} onChange={(e) => setWhen(e.target.value)} /></label>
      <label>Meeting details <span className="muted">(shared with the tenant)</span><input maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Ask for Peter at the main gate" /></label>
      <p className="muted small">Approving shares the address and your phone number with this tenant, and theirs with you.</p>
      <div className="inline-actions">
        <button disabled={busy} onClick={() => void post(`/viewings/requests/${item.id}/approve/`, { scheduled_at: iso(when), meeting_note: note }, "Viewing booked. The tenant has been notified.")}>Approve viewing</button>
        <button className="button-secondary" disabled={busy} onClick={() => setMode(mode === "decline" ? "" : "decline")}>Decline</button>
      </div>
      {mode === "decline" && <div className="inline-form">
        <label>Reason for the tenant <span className="muted">(optional)</span><input maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Already let" /></label>
        <button className="button-danger button-small" disabled={busy} onClick={() => void post(`/viewings/requests/${item.id}/reject/`, { note }, "Request declined. The tenant's credit was returned.")}>Decline request</button>
      </div>}
    </div>}

    {viewing && item.status === "approved" && <p className="viewing-when"><strong>{dateTime(viewing.scheduled_at)}</strong>{viewing.meeting_note && <span className="muted"> · {viewing.meeting_note}</span>}</p>}
    {item.contact && <ContactCard contact={item.contact} who="tenant" />}

    {upcoming && <div className="inline-actions">
      <button className="button-secondary button-small" onClick={() => setMode(mode === "reschedule" ? "" : "reschedule")}>Change time</button>
      <button className="button-secondary button-small" onClick={() => setMode(mode === "cancel" ? "" : "cancel")}>Cancel viewing</button>
    </div>}
    {mode === "reschedule" && <div className="inline-form">
      <label>New time<input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></label>
      <button className="button-small" disabled={busy} onClick={() => void post(`/viewings/${viewing!.id}/reschedule/`, { scheduled_at: iso(when) }, "Viewing moved. The tenant has been notified.")}>Save new time</button>
    </div>}
    {mode === "cancel" && <div className="inline-form">
      <p className="muted small">The tenant&apos;s viewing credit is returned automatically.</p>
      <label>Reason<input maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} /></label>
      <button className="button-danger button-small" disabled={busy} onClick={() => void post(`/viewings/requests/${item.id}/cancel/`, { reason: note }, "Viewing cancelled and the tenant's credit returned.")}>Cancel viewing</button>
    </div>}

    {outcomeDue(item) && <div className="outcome-box">
      <p><strong>What happened at this viewing?</strong> If you rent to this tenant, the platform success fee applies (see Payments).</p>
      <div className="outcome-actions">{OUTCOMES.map(([choice, text]) =>
        <button key={choice} className={choice === "rented" ? "" : "button-secondary"} disabled={busy}
                onClick={() => void post(`/viewings/${viewing!.id}/outcome/`, { choice }, "Thank you. The outcome was recorded.")}>{text}</button>)}</div>
    </div>}
    {item.my_outcome && <p className="muted small">Your report: {titleCase(item.my_outcome)}</p>}
    <RequestTimeline requestId={item.id} />
  </article>;
}
