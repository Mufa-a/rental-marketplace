"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useRequireRole } from "@/lib/session";
import type { PublicListing } from "@/lib/types";
import ListingCard from "@/components/ListingCard";
import SiteHeader from "@/components/SiteHeader";

type SavedItem = { id: number; unit: PublicListing; still_available: boolean; created_at: string };

export default function SavedHomesPage() {
  const user = useRequireRole("tenant");
  const [items, setItems] = useState<SavedItem[] | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!user) return;
    apiFetch<SavedItem[]>("/properties/saved/", {}, true).then(setItems)
      .catch((error) => { setItems([]); setMessage(error instanceof Error ? error.message : "We could not load your saved homes."); });
  }, [user]);

  async function remove(unitId: number) {
    try { await apiFetch(`/properties/saved/${unitId}/`, { method: "DELETE" }, true); setItems((current) => (current ?? []).filter((item) => item.unit.id !== unitId)); }
    catch (error) { setMessage(error instanceof Error ? error.message : "We could not remove that home."); }
  }

  const available = (items ?? []).filter((i) => i.still_available);
  const gone = (items ?? []).filter((i) => !i.still_available);
  return <main className="shell">
    <SiteHeader />
    <section className="dashboard-intro"><div><p className="eyebrow">Your shortlist</p><h1>Saved homes</h1><p className="muted">Keep the rentals you like together while you decide where to view.</p></div></section>
    {message && <p className="notice notice-error" role="alert">{message}</p>}
    {items === null && <div className="listing-grid">{[1, 2, 3].map((i) => <div className="glass skeleton-card" key={i} aria-hidden="true" />)}</div>}
    {items?.length === 0 && !message && <div className="glass empty"><h2>No saved homes yet</h2><p>Tap &ldquo;Save this home&rdquo; on any listing to keep it here.</p><Link className="button" href="/">Browse rentals</Link></div>}
    {available.length > 0 && <div className="listing-grid">{available.map(({ unit }) => <div key={unit.id} className="saved-item"><ListingCard listing={unit} /><button className="button-secondary button-small" onClick={() => void remove(unit.id)}>Remove</button></div>)}</div>}
    {gone.length > 0 && <section className="results-section"><h2 className="group-title">No longer available</h2>
      <ul className="plain-list">{gone.map(({ unit }) => <li key={unit.id} className="glass gone-row"><span><strong>{unit.title}</strong> <span className="muted">· {unit.property.area}</span></span><button className="button-secondary button-small" onClick={() => void remove(unit.id)}>Remove</button></li>)}</ul>
    </section>}
  </main>;
}
