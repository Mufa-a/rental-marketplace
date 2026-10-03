"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import NearbyMap from "@/components/NearbyMap";
import SiteHeader from "@/components/SiteHeader";
import VerificationBadge from "@/components/VerificationBadge";
import HeroArt from "@/components/HeroArt";
import SafetyTips from "@/components/SafetyTips";

type Unit = {
  id: number; slug: string; title: string; monthly_rent: number; bedrooms: number; bathrooms: string; furnishing: string;
  distance_km: number | null; media: { url: string; alt_text: string }[];
  property: { area: string; city: string; latitude?: number; longitude?: number; verification_status?: string };
};
type Filters = { area: string; city: string; min_rent: string; max_rent: string; bedrooms: string; unit_type: string; furnishing: string; amenity: string; ordering: string };
const DEFAULT_FILTERS: Filters = { area: "", city: "", min_rent: "", max_rent: "", bedrooms: "", unit_type: "", furnishing: "", amenity: "", ordering: "-created_at" };
const FURNISHING_LABELS: Record<string, string> = { furnished: "Furnished", unfurnished: "Unfurnished", semi_furnished: "Semi-furnished" };
const POPULAR_AREAS = ["Kilimani", "Westlands", "Kileleshwa", "Lavington", "Kasarani", "Ruaka", "Syokimau", "Nyali"];
const STEPS = [
  { title: "Search your way", body: "Filter by area, rent, bedrooms and amenities, or let us find homes near your current location." },
  { title: "Request a viewing", body: "Pick a home you like and ask the landlord for a time. Every request is tracked from your dashboard." },
  { title: "Meet and decide", body: "See the place in person. Rent, deposit and lease are agreed directly between you and the landlord." },
];
const hasActiveFilters = (active: Filters, location: unknown) =>
  Boolean(location) || Object.entries(active).some(([key, value]) => key !== "ordering" && value.trim());

function HomeGlyph() {
  return <svg viewBox="0 0 64 64" width="56" height="56" fill="none" stroke="rgba(255,255,255,.72)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><path d="M8 30 32 10l24 20" /><path d="M14 27v27h36V27" /><path d="M27 54V38h10v16" /></svg>;
}
type Amenity = { id: number; name: string; slug: string };
type Results = { results: Unit[]; count: number; next: string | null };

export default function Home() {
  const [units, setUnits] = useState<Unit[]>([]);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [failed, setFailed] = useState(false);
  const [amenities, setAmenities] = useState<Amenity[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [nearby, setNearby] = useState<{ latitude: number; longitude: number } | null>(null);
  const [radiusKm, setRadiusKm] = useState("10");
  const [mapVisible, setMapVisible] = useState(false);
  const [locating, setLocating] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  async function search(event?: FormEvent, requestedPage = 1, append = false, location = nearby, override?: Filters) {
    event?.preventDefault();
    const active = override ?? filters;
    setLoading(true); setError(""); setFailed(false); setSearched(true);
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(active)) if (value.trim()) query.set(key, value.trim());
    if (location) {
      query.set("latitude", String(location.latitude));
      query.set("longitude", String(location.longitude));
      query.set("radius_km", radiusKm);
      query.set("ordering", "distance");
    }
    query.set("page", String(requestedPage));
    try {
      const data = await apiFetch<Results>(`/properties/search/?${query.toString()}`);
      setUnits(current => append ? [...current, ...data.results] : data.results);
      setPage(requestedPage); setHasMore(Boolean(data.next));
    } catch (err) {
      setUnits([]); setFailed(true); setError(err instanceof Error ? err.message : "We could not load homes. Check your connection and try again.");
    } finally { setLoading(false); }
  }

  function findNearby() {
    if (!navigator.geolocation) { setError("Location search is not available in this browser."); return; }
    setLocating(true); setError("");
    navigator.geolocation.getCurrentPosition(position => {
      const location = { latitude: position.coords.latitude, longitude: position.coords.longitude };
      setNearby(location);
      setLocating(false);
      void search(undefined, 1, false, location);
    }, () => {
      setLocating(false);
      setError("We could not access your location. Allow location permission or search by area instead.");
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
  }

  function pickArea(area: string) {
    const next = { ...filters, area };
    setFilters(next);
    void search(undefined, 1, false, nearby, next);
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function clearFilters() {
    setFilters(DEFAULT_FILTERS); setNearby(null); setMapVisible(false);
    void search(undefined, 1, false, null, DEFAULT_FILTERS);
  }

  const filtered = hasActiveFilters(filters, nearby);

  useEffect(() => {
    void search();
    apiFetch<Amenity[]>("/properties/amenities/").then(setAmenities).catch(() => setAmenities([]));
  }, []);

  return <main className="shell">
    <SiteHeader right={<><Link className="navlink" href="/login">Sign in</Link><Link className="button button-small" href="/login">Create account</Link></>} />
    <section className="hero-v2 glass">
      <div className="hero-v2-top">
        <div className="hero-v2-copy">
          <span className="hero-pill"><i />A clearer way to rent in Kenya</span>
          <h1>Find a place that feels like <em>home.</em></h1>
          <p className="muted">Browse real rentals with clear monthly prices, then arrange viewings directly with the landlord. No guesswork, no middle layers.</p>
        </div>
        <HeroArt />
      </div>
      <form onSubmit={search} className="search-panel" aria-label="Search available rentals">
        <button className="button button-secondary" type="button" onClick={findNearby} disabled={loading || locating}>{locating ? "Finding your location…" : "Homes near me"}</button>
        {nearby && <><label>Search radius<select value={radiusKm} onChange={event => setRadiusKm(event.target.value)}><option value="5">Within 5 km</option><option value="10">Within 10 km</option><option value="25">Within 25 km</option><option value="50">Within 50 km</option></select></label><button className="button button-secondary" type="button" onClick={() => { setNearby(null); void search(undefined, 1, false, null); }}>Clear nearby</button></>}
        <label className="area-field">Area<input value={filters.area} onChange={e => setFilters({ ...filters, area: e.target.value })} placeholder="Westlands, Nyali…" /></label>
        <button type="button" className="button button-secondary mobile-filter-trigger" onClick={() => setFiltersOpen(true)}>More filters</button>
        {filtersOpen && <div className="sheet-backdrop" onClick={() => setFiltersOpen(false)} aria-hidden="true" />}
        <div className={`filter-sheet${filtersOpen ? " is-open" : ""}`} role="group" aria-label="Additional filters">
          <div className="filter-sheet-head"><strong>Filters</strong><button type="button" className="sheet-close" onClick={() => setFiltersOpen(false)} aria-label="Close filters">✕</button></div>
          <label>City<input value={filters.city} onChange={e => setFilters({ ...filters, city: e.target.value })} placeholder="Nairobi" /></label>
          <label>Min. rent<input type="number" min="0" value={filters.min_rent} onChange={e => setFilters({ ...filters, min_rent: e.target.value })} placeholder="KSh" /></label>
          <label>Max. rent<input type="number" min="1" value={filters.max_rent} onChange={e => setFilters({ ...filters, max_rent: e.target.value })} placeholder="KSh" /></label>
          <label>Bedrooms<select value={filters.bedrooms} onChange={e => setFilters({ ...filters, bedrooms: e.target.value })}><option value="">Any</option>{[0,1,2,3,4].map(n => <option value={n} key={n}>{n === 0 ? "Bedsitter / studio" : `${n}+`}</option>)}</select></label>
          <label>Home type<select value={filters.unit_type} onChange={e => setFilters({ ...filters, unit_type: e.target.value })}><option value="">Any type</option><option value="bedsitter">Bedsitter</option><option value="studio">Studio</option><option value="apartment">Apartment</option><option value="house">House</option><option value="maisonette">Maisonette</option><option value="room">Room</option></select></label>
          <label>Furnishing<select value={filters.furnishing} onChange={e => setFilters({ ...filters, furnishing: e.target.value })}><option value="">Any</option><option value="furnished">Furnished</option><option value="unfurnished">Unfurnished</option><option value="semi_furnished">Semi-furnished</option></select></label>
          <label>Amenity<select value={filters.amenity} onChange={e => setFilters({ ...filters, amenity: e.target.value })}><option value="">Any</option>{amenities.map(item => <option value={item.slug} key={item.id}>{item.name}</option>)}</select></label>
          <label>Sort by<select value={nearby ? "distance" : filters.ordering} onChange={e => setFilters({ ...filters, ordering: e.target.value })} disabled={Boolean(nearby)}><option value="-created_at">Newest</option><option value="monthly_rent">Price: low to high</option><option value="-monthly_rent">Price: high to low</option><option value="bedrooms">Bedrooms</option><option value="distance" disabled={!nearby}>Nearest first (use Homes near me)</option></select></label>
          <button type="button" className="button sheet-apply" onClick={() => { setFiltersOpen(false); void search(); }}>Show homes</button>
        </div>
        <button className="button search-button" type="submit" disabled={loading}>{loading ? "Searching…" : "Find homes"}</button>
      </form>
      <div className="area-row" role="group" aria-label="Popular areas"><span>Popular areas</span>{POPULAR_AREAS.map(area => <button type="button" className="chip" key={area} aria-pressed={filters.area.toLowerCase() === area.toLowerCase()} onClick={() => pickArea(area)}>{area}</button>)}</div>
    </section>
    <section className="results-section" id="results"><div className="section-heading"><div><p className="eyebrow">Available rentals</p><h2>{nearby ? "Homes around you" : searched ? "Homes for you" : "Explore homes"}</h2></div><div className="results-tools"><span className="muted">{units.length} {units.length === 1 ? "home" : "homes"} shown</span>{nearby && <button className="button-secondary" type="button" onClick={() => setMapVisible(value => !value)}>{mapVisible ? "See list" : "See map"}</button>}</div></div>
      {error && <div className="notice" role="status">{error}</div>}
      {loading && <div className="listing-grid">{[1,2,3].map(i => <div className="glass skeleton-card" key={i} aria-label="Loading home" />)}</div>}
      {!loading && nearby && mapVisible && <NearbyMap units={units} center={nearby} />}
      {!loading && units.length > 0 && <div className="listing-grid">{units.map(unit => <Link key={unit.id} href={`/listings/${encodeURIComponent(unit.property.city.toLowerCase())}/${encodeURIComponent(unit.property.area.toLowerCase())}/${unit.slug}`} className="glass listing-card">
        {unit.media[0]?.url ? <img className="listing-image" src={unit.media[0].url} alt={unit.media[0].alt_text || `${unit.title} rental home`} /> : <div className="listing-image image-placeholder" aria-hidden="true"><HomeGlyph /></div>}
        <div className="listing-card-content"><div className="badge-row"><span className="status">Available</span><VerificationBadge status={unit.property.verification_status} /></div><p className="muted location">{unit.property.area}, {unit.property.city}{unit.distance_km !== null && unit.distance_km !== undefined ? ` · ${unit.distance_km} km away` : ""}</p><h3>{unit.title}</h3><strong className="price">KSh {unit.monthly_rent.toLocaleString()} <span>/ month</span></strong><p className="muted">{unit.bedrooms === 0 ? "Bedsitter" : `${unit.bedrooms} bedroom${unit.bedrooms === 1 ? "" : "s"}`} · {unit.bathrooms} bath · {FURNISHING_LABELS[unit.furnishing] ?? unit.furnishing}</p></div>
      </Link>)}</div>}
      {!loading && units.length === 0 && <div className="glass empty empty-state"><HomeGlyph /><h3>{failed ? "Couldn't load homes" : filtered ? "No matching homes" : "No homes listed yet"}</h3><p>{failed ? "Check that the backend is running, then try again." : filtered ? "Nothing matches those filters right now. Try a wider area or rent range." : "New rentals appear here as landlords publish them. Check back soon, or list your own."}</p><div className="empty-actions">{filtered && <button type="button" className="button button-secondary" onClick={clearFilters}>Clear filters</button>}{failed && <button type="button" className="button button-secondary" onClick={() => void search()}>Try again</button>}<Link className="button button-small" href="/login">List a home</Link></div></div>}
      {!loading && searched && units.length > 0 && hasMore && <button className="button button-secondary load-more" onClick={() => void search(undefined, page + 1, true)}>Show more homes</button>}
    </section>
    <section className="how" aria-labelledby="how-title">
      <div className="how-head"><p className="eyebrow">How it works</p><h2 id="how-title">From search to keys, in three clear steps.</h2></div>
      <div className="steps">{STEPS.map((step, index) => <article className="glass step" key={step.title}><span className="step-num" aria-hidden="true">{index + 1}</span><h3>{step.title}</h3><p>{step.body}</p></article>)}</div>
    </section>
    <section className="audience" aria-label="For tenants and landlords">
      <article className="glass audience-card"><p className="eyebrow">For tenants</p><h2>Look freely, ask when you are ready</h2><ul><li>Browse homes for free, with the monthly rent up front.</li><li>Request a viewing and follow its status from your dashboard.</li><li>Agree rent, deposit and lease directly with the landlord.</li></ul><Link className="button button-small" href="/login">Create a tenant account</Link></article>
      <article className="glass audience-card"><p className="eyebrow">For landlords</p><h2>Reach tenants who want to view</h2><ul><li>List each unit with photos, rent and availability.</li><li>Approve or decline viewing requests and schedule the time.</li><li>Every request and outcome is recorded for both sides.</li></ul><Link className="button button-small" href="/login">List a home</Link></article>
    </section>
    <section className="glass trust-section" aria-labelledby="trust-title">
      <div className="how-head"><p className="eyebrow">Trust &amp; safety</p><h2 id="trust-title">Rent with your eyes open.</h2><p className="muted">Nyumbani connects tenants and landlords. We do not own or inspect the homes, so a few habits keep everyone safe.</p></div>
      <SafetyTips compact />
    </section>
    <section className="glass cta-band"><div><h2>Own a property in Kenya?</h2><p>List your units, receive viewing requests from real tenants, and manage everything from one dashboard.</p></div><Link className="button" href="/login">List a home</Link></section>
  </main>;
}
