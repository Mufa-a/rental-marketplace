"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { bedroomsLabel, date, money, plural, titleCase } from "@/lib/format";
import { newIdempotencyKey, usePaymentStatus } from "@/lib/payments";
import { useRequireRole } from "@/lib/session";
import { slug } from "@/lib/search";
import { outcomeDue } from "@/lib/status";
import type { Amenity, Payment, ViewingRequest } from "@/lib/types";
import ListingForm from "@/components/landlord/ListingForm";
import RequestCard from "@/components/landlord/RequestCard";
import VerificationPanel from "@/components/landlord/VerificationPanel";
import type { Fee, OwnProperty, OwnUnit, Stats } from "@/components/landlord/types";
import PaymentStatusNotice from "@/components/PaymentStatusNotice";
import PropertyLocationEditor from "@/components/PropertyLocationEditor";
import SiteHeader from "@/components/SiteHeader";
import VerificationBadge from "@/components/VerificationBadge";

type Tab = "overview" | "homes" | "viewings" | "payments" | "verification";
type Listing = { property: OwnProperty; units: OwnUnit[] };

const MODERATION: Record<string, string> = { approved: "", pending_review: "Waiting for review", changes_requested: "Changes requested", rejected: "Not approved" };

function unitState(unit: OwnUnit) {
  if (unit.moderation_hold) return { text: "On hold by Nyumbani", tone: "status-danger" };
  if (MODERATION[unit.moderation_status]) return { text: MODERATION[unit.moderation_status], tone: "status-warning" };
  if (!unit.available) return { text: "Occupied", tone: "status-paused" };
  if (!unit.is_published) return { text: "Draft / paused", tone: "status-paused" };
  const stale = unit.availability_confirmed_at && Date.now() - new Date(unit.availability_confirmed_at).getTime() > 30 * 86400000;
  return stale ? { text: "Hidden — confirm availability", tone: "status-warning" } : { text: "Live in search", tone: "" };
}

export default function LandlordDashboard() {
  const user = useRequireRole("landlord");
  const [tab, setTab] = useState<Tab>("overview");
  const [listings, setListings] = useState<Listing[] | null>(null);
  const [requests, setRequests] = useState<ViewingRequest[]>([]);
  const [fees, setFees] = useState<Fee[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [amenities, setAmenities] = useState<Amenity[]>([]);
  const [verificationFee, setVerificationFee] = useState<number | null>(null);
  const [form, setForm] = useState<{ unit?: OwnUnit; propertyId?: number } | null>(null);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const [payPhone, setPayPhone] = useState("");
  const payment = usePaymentStatus((p: Payment) => { if (p.status === "successful") void load(); });

  const load = useCallback(async () => {
    try {
      const [properties, viewingRequests, referralFees, performance] = await Promise.all([
        apiFetch<OwnProperty[]>("/properties/mine/", {}, true),
        apiFetch<ViewingRequest[]>("/viewings/requests/", {}, true),
        apiFetch<Fee[]>("/referrals/mine/", {}, true),
        apiFetch<Stats>("/properties/mine/stats/", {}, true),
      ]);
      const entries = await Promise.all(properties.map(async (property) => ({ property, units: await apiFetch<OwnUnit[]>(`/properties/${property.id}/units/`, {}, true) })));
      setListings(entries); setRequests(viewingRequests); setFees(referralFees); setStats(performance);
    } catch (error) { setMessage({ text: error instanceof Error ? error.message : "We could not load your dashboard.", error: true }); setListings([]); }
  }, []);

  useEffect(() => {
    if (!user) return;
    setPayPhone(user.phone_number.replace(/^\+254/, "0"));
    const wanted = new URLSearchParams(window.location.search).get("tab") as Tab | null;
    if (wanted) setTab(wanted);
    void load();
    apiFetch<Amenity[]>("/properties/amenities/").then(setAmenities).catch(() => undefined);
    apiFetch<{ property_verification_fee: { amount: number } | null }>("/payments/prices/").then((p) => setVerificationFee(p.property_verification_fee?.amount ?? null)).catch(() => undefined);
  }, [user, load]);

  const notify = (text: string, error = false) => { setMessage({ text, error }); if (!error) void load(); window.scrollTo({ top: 0, behavior: "smooth" }); };

  async function call(path: string, method: string, body: object | undefined, success: string) {
    try { await apiFetch(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }, true); notify(success); }
    catch (error) { notify(error instanceof Error ? error.message : "That did not work.", true); }
  }

  async function startPayment(path: string) {
    try {
      const started = await apiFetch<Payment>(path, { method: "POST", body: JSON.stringify({ phone_number: payPhone, idempotency_key: newIdempotencyKey() }) }, true);
      payment.track(started);
    } catch (error) { notify(error instanceof Error ? error.message : "We could not start the M-Pesa payment.", true); }
  }

  if (!user) return <main className="shell"><div className="glass empty" aria-busy="true">Loading…</div></main>;
  const pending = requests.filter((r) => r.status === "pending_landlord");
  const due = requests.filter(outcomeDue);
  const upcoming = requests.filter((r) => r.status === "approved" && r.viewing?.status === "scheduled" && new Date(r.viewing.scheduled_at).getTime() > Date.now());
  const others = requests.filter((r) => !pending.includes(r) && !due.includes(r) && !upcoming.includes(r));
  const unpaid = fees.filter((f) => f.status === "pending");
  const t = stats?.totals;

  const tabs: [Tab, string][] = [["overview", "Overview"], ["homes", "Homes"], ["viewings", `Viewings${pending.length + due.length ? ` (${pending.length + due.length})` : ""}`], ["payments", `Payments${unpaid.length ? ` (${unpaid.length})` : ""}`], ["verification", "Verification"]];

  return <main className="shell">
    <SiteHeader />
    <section className="dashboard-intro">
      <div><p className="eyebrow">Landlord dashboard</p><h1>Your homes</h1><p className="muted">Listings, viewing requests and results in one place.</p></div>
      <button onClick={() => { setTab("homes"); setForm({}); }}>Add a home</button>
    </section>
    <nav className="tabbar" role="tablist" aria-label="Dashboard sections">{tabs.map(([id, text]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => { setTab(id); setForm(null); }}>{text}</button>)}</nav>
    {message && <p className={`notice ${message.error ? "notice-error" : "notice-success"}`} role="status" aria-live="polite">{message.text}</p>}
    {listings === null && <div className="glass skeleton-card short" aria-busy="true" />}

    {tab === "overview" && listings && <>
      {(pending.length > 0 || due.length > 0 || unpaid.length > 0) && <section className="glass activity-card outcome-first">
        <p className="eyebrow">Needs your attention</p>
        <ul className="todo">
          {pending.length > 0 && <li><button className="linklike" onClick={() => setTab("viewings")}>{plural(pending.length, "viewing request")} waiting for your reply</button> — unanswered requests expire after 7 days.</li>}
          {due.length > 0 && <li><button className="linklike" onClick={() => setTab("viewings")}>{plural(due.length, "viewing")} need an outcome report</button>.</li>}
          {unpaid.length > 0 && <li><button className="linklike" onClick={() => setTab("payments")}>{plural(unpaid.length, "success fee")} to pay</button>.</li>}
        </ul>
      </section>}
      {t && <section className="admin-metrics" aria-label="Last 30 days">
        {([["Listing views (30 days)", t.views_30d], ["Saved by tenants", t.saves], ["Viewing requests", t.requests], ["Approved viewings", t.approved], ["Completed viewings", t.completed], ["Rentals", t.rented]] as [string, number][]).map(([label, value]) =>
          <article className="glass admin-metric" key={label}><span className="muted">{label}</span><strong>{value}</strong></article>)}
      </section>}
      {stats && stats.units.length > 0 ? <section className="glass table-wrap" aria-labelledby="perf-title">
        <h2 id="perf-title" className="table-title">Listing performance</h2>
        <table className="data-table">
          <thead><tr><th scope="col">Home</th><th scope="col">Status</th><th scope="col">Views 7d</th><th scope="col">Views 30d</th><th scope="col">Saves</th><th scope="col">Requests</th><th scope="col">Completed</th><th scope="col">Rented</th></tr></thead>
          <tbody>{stats.units.map((u) => <tr key={u.unit_id}><td><strong>{u.title}</strong><br /><span className="muted small">{u.property}</span></td><td>{u.visible_in_search ? "Live" : MODERATION[u.moderation_status] || "Not in search"}</td><td>{u.views_7d}</td><td>{u.views_30d}</td><td>{u.saves}</td><td>{u.requests}</td><td>{u.completed}</td><td>{u.rented}</td></tr>)}</tbody>
        </table>
        {t?.request_rate != null && <p className="muted small">{Math.round(t.request_rate * 100)}% of views turned into a viewing request in the last 30 days. Clear photos and accurate rent usually raise this.</p>}
      </section> : listings.length === 0 && <div className="glass empty"><h3>List your first home</h3><p>Listing is free. Tenants request viewings; you approve the ones that suit you.</p><button onClick={() => { setTab("homes"); setForm({}); }}>Add a home</button></div>}
    </>}

    {tab === "homes" && listings && <section className="dashboard-content">
      {form && <section className="glass form-panel"><h2>{form.unit ? `Edit “${form.unit.title}”` : "New listing"}</h2>
        <ListingForm properties={listings.map((l) => l.property)} amenities={amenities} unit={form.unit} defaultPropertyId={form.propertyId}
                     onDone={(text) => { setForm(null); notify(text); }} onCancel={() => setForm(null)} /></section>}
      {listings.length === 0 && !form && <div className="glass empty"><h3>No homes yet</h3><button onClick={() => setForm({})}>Add a home</button></div>}
      {listings.map(({ property, units }) => <section className="glass owner-property" key={property.id}>
        <div className="activity-heading">
          <div><h3>{property.name}</h3><p className="muted">{property.address_line} · {property.area}, {property.city}</p></div>
          <button type="button" className="button-secondary button-small" onClick={() => setForm({ propertyId: property.id })}>Add a unit</button>
        </div>
        <div className="verify-box">
          <VerificationBadge status={property.verification_status} showUnverified />
          {property.verification_status === "pending" && <span className="muted small">Our team is reviewing this property.</span>}
          {property.verification_status === "needs_review" && <span className="muted small">The address changed, so we will re-check it (no extra fee).</span>}
          {["unverified", "rejected", "needs_review"].includes(property.verification_status) && verificationFee != null &&
            <button className="button-secondary button-small" onClick={() => void startPayment(`/payments/property-verification/${property.id}/pay/`)}>
              {property.verification_status === "unverified" ? `Request property verification · ${money(verificationFee)}` : "Resubmit for review"}</button>}
        </div>
        <PropertyLocationEditor propertyId={property.id} latitude={property.latitude} longitude={property.longitude} onSaved={() => void load()} />
        {units.length === 0 && <p className="muted">No units yet.</p>}
        {units.map((unit) => { const state = unitState(unit); return <article className="owner-unit-wrap" key={unit.id}>
          <div className="owner-unit">
            <div>
              <strong>{unit.title}</strong>
              <p className="muted small">Unit {unit.unit_number} · {money(unit.monthly_rent)}/month · {bedroomsLabel(unit.bedrooms, unit.unit_type)} · {plural(unit.media.length, "photo")}</p>
              <span className={`status ${state.tone}`}>{state.text}</span>
              {unit.moderation_note && unit.moderation_status !== "approved" && <p className="notice notice-warning small">{unit.moderation_note}</p>}
              {unit.available && unit.availability_confirmed_at && <p className="muted small">Availability confirmed {date(unit.availability_confirmed_at)}</p>}
            </div>
            <div className="owner-actions">
              <button className="button-secondary button-small" onClick={() => setForm({ unit })}>Edit</button>
              {unit.available
                ? <><button className="button-secondary button-small" onClick={() => void call(`/properties/units/${unit.id}/availability/`, "POST", { available: true }, "Availability confirmed for another 30 days.")}>Still available</button>
                    <button className="button-secondary button-small" onClick={() => { if (window.confirm("Mark this home as occupied? It leaves search, open requests are closed and recent viewers are asked whether they rented it.")) void call(`/properties/units/${unit.id}/availability/`, "POST", { available: false }, "Marked as occupied and removed from search."); }}>Mark occupied</button></>
                : <button className="button-secondary button-small" onClick={() => void call(`/properties/units/${unit.id}/availability/`, "POST", { available: true }, "Marked available again.")}>Available again</button>}
              <button className="button-secondary button-small" disabled={unit.moderation_hold} onClick={() => void call(`/properties/units/${unit.id}/`, "PATCH", { is_published: !unit.is_published }, unit.is_published ? "Listing paused." : "Listing published.")}>{unit.is_published ? "Pause" : "Publish"}</button>
              <button className="button-danger button-small" onClick={() => { if (window.confirm(`Delete “${unit.title}”? Homes with viewing history can only be paused.`)) void call(`/properties/units/${unit.id}/`, "DELETE", undefined, "Listing deleted."); }}>Delete</button>
              {unitState(unit).text === "Live in search" && <Link className="navlink small" href={`/listings/${slug(property.city)}/${slug(property.area)}/${unit.slug}`}>View</Link>}
            </div>
          </div>
        </article>; })}
      </section>)}
    </section>}

    {tab === "viewings" && <section className="dashboard-content">
      {([["Waiting for your reply", pending], ["Report the outcome", due], ["Upcoming viewings", upcoming], ["Earlier", others]] as [string, ViewingRequest[]][])
        .filter(([, list]) => list.length).map(([heading, list]) => <div key={heading}><h2 className="group-title">{heading} <span className="muted">({list.length})</span></h2>
          {list.map((item) => <RequestCard key={item.id} item={item} onChanged={notify} />)}</div>)}
      {requests.length === 0 && <div className="glass empty"><h3>No viewing requests yet</h3><p>When tenants ask to view your homes, their requests appear here.</p></div>}
    </section>}

    {tab === "payments" && <section className="dashboard-content">
      <div className="glass form-panel">
        <h2>Success fees</h2>
        <p className="muted">A success fee is owed only when a tenant you met through a Nyumbani viewing rents your home. Listing and viewings are free for landlords. <Link href="/viewing-packages#landlord-fees">How fees are calculated</Link>.</p>
        <label className="narrow-field">M-Pesa number for prompts<input type="tel" inputMode="tel" value={payPhone} onChange={(e) => setPayPhone(e.target.value)} /></label>
        {payment.payment && <PaymentStatusNotice payment={payment.payment} onRefresh={() => void payment.refresh()} />}
      </div>
      {fees.length === 0 && <div className="glass empty">No success fees yet.</div>}
      {fees.map((fee) => <article className="glass activity-card" key={fee.id}>
        <div className="activity-heading">
          <div><span className={`status ${fee.status === "pending" ? "status-warning" : ""}`}>{titleCase(fee.status)}</span><h3>{fee.unit_title}</h3>
            <p className="muted">{money(fee.amount, fee.currency)}{fee.monthly_rent ? ` (rent ${money(fee.monthly_rent)})` : ""}{fee.due_at && fee.status === "pending" ? ` · due ${date(fee.due_at)}` : ""}{fee.paid_at ? ` · paid ${date(fee.paid_at)}` : ""}</p></div>
          {fee.status === "pending" && <button disabled={!payPhone.trim() || payment.payment?.status === "pending"} onClick={() => void startPayment(`/payments/referral-fees/${fee.id}/pay/`)}>Pay with M-Pesa</button>}
        </div>
        {fee.status === "pending" && <p className="muted small">Think this is wrong? Reply to the outcome on the viewing or contact support before the due date — fees can be reviewed or waived.</p>}
      </article>)}
    </section>}

    {tab === "verification" && <section className="dashboard-content"><VerificationPanel /></section>}
  </main>;
}
