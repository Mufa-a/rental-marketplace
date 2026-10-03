"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, signOut } from "@/lib/api";
import ViewingCreditShop from "@/components/ViewingCreditShop";
import SiteHeader from "@/components/SiteHeader";
import StatusBadge from "@/components/StatusBadge";
import { requestStage } from "@/lib/status";

type Request = { id: number; status: string; note: string; created_at: string; unit: number; unit_title: string; property_name: string; area: string; monthly_rent: number; landlord_note: string; responded_at: string | null; unit_available: boolean; viewing: { id: number; scheduled_at: string; status: string } | null };
const label = (status: string) => status.replaceAll("_", " ").replace(/^./, s => s.toUpperCase());

export default function TenantDashboard() {
  const [items, setItems] = useState<Request[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [credits, setCredits] = useState<number | null>(null);
  async function cancelRequest(requestId: number) {
    try { await apiFetch(`/viewings/requests/${requestId}/cancel/`, { method: "POST", body: JSON.stringify({}) }, true); setMessage("Your viewing request was cancelled."); setItems(await apiFetch<Request[]>("/viewings/requests/", {}, true)); }
    catch (error) { setMessage(error instanceof Error ? error.message : "We could not cancel that request."); }
  }
  async function act(viewingId: number, action: "complete" | "outcome", choice?: string) {
    try {
      await apiFetch(`/viewings/${viewingId}/${action}/`, { method: "POST", body: JSON.stringify(action === "outcome" ? { choice } : {}) }, true);
      setMessage(action === "complete" ? "Viewing marked complete. Please report the outcome when you are ready." : "Thanks. Your outcome was recorded.");
      const updated = await apiFetch<Request[]>("/viewings/requests/", {}, true); setItems(updated);
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not update the viewing."); }
  }
  useEffect(() => {
    const current = localStorage.getItem("rental_user");
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    let role = "";
    try { role = current ? JSON.parse(current).role : ""; } catch { localStorage.removeItem("rental_user"); }
    if (role && role !== "tenant") { window.location.assign(role === "admin" ? "/admin" : "/landlord"); return; }
    apiFetch<Request[]>("/viewings/requests/", {}, true).then(setItems)
      .catch(error => setMessage(error instanceof Error ? error.message : "We could not load your activity."))
      .finally(() => setLoading(false));
    apiFetch<{ balance: number }>("/payments/viewing-credits/", {}, true)
      .then(data => setCredits(Number(data.balance)))
      .catch(() => setCredits(null));
  }, []);

  const reportsDue = items.filter(item => item.viewing && (item.viewing.status === "outcome_pending" || (item.viewing.status === "scheduled" && new Date(item.viewing.scheduled_at).getTime() <= Date.now())));
  return <main className="shell"><SiteHeader right={<><Link className="navlink" href="/">Browse homes</Link><Link className="navlink" href="/saved">Saved homes</Link><Link className="navlink" href="/profile">Profile</Link><button className="button-secondary" onClick={signOut}>Sign out</button></>} />
    {reportsDue.length > 0 && <section className="glass activity-card outcome-first"><p className="eyebrow">Action needed first</p><h2>Tell us what happened at your viewing</h2><p className="muted">Your report helps us keep listings accurate. Your report helps us verify the outcome; the landlord’s rental report removes a rented unit from search.</p>{reportsDue.map(item => <div className="outcome-first-row" key={item.viewing!.id}><div><strong>{item.unit_title}</strong><p className="muted">{item.property_name} · {new Date(item.viewing!.scheduled_at).toLocaleString()}</p></div><div className="outcome-actions"><button className="button-secondary" onClick={() => void act(item.viewing!.id, "outcome", "did_not_rent")}>I did not rent</button><button className="button-secondary" onClick={() => void act(item.viewing!.id, "outcome", "still_deciding")}>Still deciding</button></div></div>)}</section>}
    <section className="dashboard-intro"><p className="eyebrow">Tenant dashboard</p><h1>Your viewings</h1><p className="muted">Follow your requests and see landlord responses in one place.</p><p className="credit-balance">Viewing credits: <strong>{credits ?? "…"}</strong></p><Link className="button" href="/">Find a home</Link></section>
    <section className="dashboard-content"><ViewingCreditShop /><div className="section-heading"><div><p className="eyebrow">Your activity</p><h2>Viewing requests</h2></div><span className="muted">{items.length} total</span></div>
      {loading && <div className="glass empty">Loading your activity…</div>}
      {!loading && message && <div className="notice" role="alert">{message}</div>}
      {!loading && !message && items.length === 0 && <div className="glass empty"><h3>No requests yet</h3><p>When you request a viewing, the landlord’s reply will appear here.</p><Link className="button" href="/">Browse available homes</Link></div>}
      {!loading && items.map(item => { const stage = requestStage(item.status, item.viewing); return <article className="glass activity-card" key={item.id}><div className="activity-heading"><div><StatusBadge label={stage.label} tone={stage.tone} /><h3>{item.unit_title || `Home #${item.unit}`}</h3><p className="muted">{item.property_name}{item.area ? ` · ${item.area}` : ""}{item.monthly_rent ? ` · KSh ${item.monthly_rent.toLocaleString()} / month` : ""}</p></div><time className="muted">{new Date(item.created_at).toLocaleDateString()}</time></div><p className="next-step">{stage.next}</p>{["pending_landlord", "approved"].includes(item.status) && !item.unit_available && <p className="notice" role="status">This home is no longer marked as available. Check with the landlord before you go.</p>}<p className="muted">{item.note || "No message added."}</p><p className="request-timeline muted">Requested {new Date(item.created_at).toLocaleString()}{item.responded_at ? ` · Landlord replied ${new Date(item.responded_at).toLocaleString()}` : ""}</p>{item.landlord_note && <p className="landlord-response"><strong>Landlord response:</strong> {item.landlord_note}</p>}{item.viewing && <div className="viewing-summary"><strong>Viewing: {label(item.viewing.status)}</strong><p className="muted">Scheduled for {new Date(item.viewing.scheduled_at).toLocaleString()}</p>{item.viewing.status === "scheduled" && <button className="button-secondary" onClick={() => void act(item.viewing!.id, "complete")}>Mark viewing complete</button>}{item.viewing.status === "outcome_pending" && <p className="muted">Please submit your viewing report at the top of this page.</p>}</div>}{["pending_landlord", "approved"].includes(item.status) && <button className="button-secondary cancel-request" onClick={() => void cancelRequest(item.id)}>Cancel request</button>}</article>; })}
    </section>
  </main>;
}
