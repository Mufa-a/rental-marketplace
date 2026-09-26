"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type SavedItem = { id: number; unit_id: number; created_at: string; unit: { id: number; slug: string; title: string; monthly_rent: number; bedrooms: number; bathrooms: string; media: { url: string; alt_text: string }[]; property: { area: string; city: string } } };

export default function SavedHomesPage() {
  const [items, setItems] = useState<SavedItem[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    apiFetch<SavedItem[]>("/properties/saved/", {}, true).then(setItems)
      .catch(error => setMessage(error instanceof Error ? error.message : "We could not load your saved homes."))
      .finally(() => setLoading(false));
  }, []);

  async function remove(unitId: number) {
    try { await apiFetch(`/properties/saved/${unitId}/`, { method: "DELETE" }, true); setItems(current => current.filter(item => item.unit.id !== unitId)); }
    catch (error) { setMessage(error instanceof Error ? error.message : "We could not remove that home."); }
  }

  return <main className="shell"><header className="topnav"><Link className="brand" href="/">Nyumbani</Link><nav className="nav-actions"><Link className="navlink" href="/tenant">Dashboard</Link><Link className="navlink" href="/profile">Profile</Link></nav></header><section className="dashboard-intro"><p className="eyebrow">Your shortlist</p><h1>Saved homes</h1><p className="muted">Keep the rentals you like together while you decide where to view.</p></section>{message && <p className="notice" role="alert">{message}</p>}{loading && <div className="glass empty">Loading your saved homes…</div>}{!loading && items.length === 0 && !message && <div className="glass empty"><h2>No saved homes yet</h2><p>Save a rental from its details page to keep it here.</p><Link className="button" href="/">Browse rentals</Link></div>}<div className="listing-grid">{items.map(({ unit }) => <article key={unit.id} className="glass saved-card"><Link className="saved-card-link" href={`/listings/${encodeURIComponent(unit.property.city.toLowerCase())}/${encodeURIComponent(unit.property.area.toLowerCase())}/${unit.slug}`}>{unit.media[0]?.url ? <img className="listing-image" src={unit.media[0].url} alt={unit.media[0].alt_text || unit.title} /> : <div className="listing-image image-placeholder"><span>Nyumbani</span></div>}<div className="listing-card-content"><p className="muted location">{unit.property.area}, {unit.property.city}</p><h3>{unit.title}</h3><strong className="price">KSh {unit.monthly_rent.toLocaleString()} <span>/ month</span></strong></div></Link><button className="button-secondary saved-remove" onClick={() => void remove(unit.id)}>Remove saved home</button></article>)}</div></main>;
}
