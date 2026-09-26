"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import NearbyMap from "@/components/NearbyMap";

type Unit = {
  id: number; slug: string; title: string; monthly_rent: number; bedrooms: number; bathrooms: string;
  distance_km: number | null; media: { url: string; alt_text: string }[]; property: { area: string; city: string; latitude?: number; longitude?: number };
};
type Amenity = { id: number; name: string; slug: string };
type Results = { results: Unit[]; count: number; next: string | null };

export default function Home() {
  const [units, setUnits] = useState<Unit[]>([]);
  const [filters, setFilters] = useState({ area: "", city: "", min_rent: "", max_rent: "", bedrooms: "", unit_type: "", amenity: "", ordering: "-created_at" });
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

  async function search(event?: FormEvent, requestedPage = 1, append = false, location = nearby) {
    event?.preventDefault();
    setLoading(true); setError(""); setSearched(true);
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) if (value.trim()) query.set(key === "area" ? "area" : key, value.trim());
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
      if (data.results.length === 0 && !append) setError("No homes match those filters. Try a wider area or rent range.");
    } catch (err) {
      setUnits([]); setError(err instanceof Error ? err.message : "We could not load homes. Check your connection and try again.");
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

  useEffect(() => {
    void search();
    apiFetch<Amenity[]>("/properties/amenities/").then(setAmenities).catch(() => setAmenities([]));
  }, []);

  return <main className="shell">
    <header className="topnav"><Link className="brand" href="/">Nyumbani</Link><nav className="nav-actions"><Link className="navlink" href="/login">Sign in</Link><Link className="button button-small" href="/login">Create account</Link></nav></header>
    <section className="hero glass"><div className="hero-copy"><p className="eyebrow">A clearer way to rent in Kenya</p><h1>Find a place that feels like home.</h1><p className="muted">Explore real rental homes, see clear monthly prices, and arrange viewings directly with landlords.</p></div>
      <form onSubmit={search} className="search-panel" aria-label="Search available rentals">
        <button className="button button-secondary" type="button" onClick={findNearby} disabled={loading || locating}>{locating ? "Finding your location…" : "Homes near me"}</button>
        {nearby && <><label>Search radius<select value={radiusKm} onChange={event => setRadiusKm(event.target.value)}><option value="5">Within 5 km</option><option value="10">Within 10 km</option><option value="25">Within 25 km</option><option value="50">Within 50 km</option></select></label><button className="button button-secondary" type="button" onClick={() => { setNearby(null); void search(undefined, 1, false, null); }}>Clear nearby</button></>}
        <label>Area<input value={filters.area} onChange={e => setFilters({ ...filters, area: e.target.value })} placeholder="Westlands, Nyali…" /></label>
        <label>City<input value={filters.city} onChange={e => setFilters({ ...filters, city: e.target.value })} placeholder="Nairobi" /></label>
        <label>Min. rent<input type="number" min="0" value={filters.min_rent} onChange={e => setFilters({ ...filters, min_rent: e.target.value })} placeholder="KSh" /></label>
        <label>Max. rent<input type="number" min="1" value={filters.max_rent} onChange={e => setFilters({ ...filters, max_rent: e.target.value })} placeholder="KSh" /></label>
        <label>Bedrooms<select value={filters.bedrooms} onChange={e => setFilters({ ...filters, bedrooms: e.target.value })}><option value="">Any</option>{[0,1,2,3,4].map(n => <option value={n} key={n}>{n === 0 ? "Bedsitter / studio" : `${n}+`}</option>)}</select></label>
        <label>Home type<select value={filters.unit_type} onChange={e => setFilters({ ...filters, unit_type: e.target.value })}><option value="">Any type</option><option value="bedsitter">Bedsitter</option><option value="studio">Studio</option><option value="apartment">Apartment</option><option value="house">House</option><option value="maisonette">Maisonette</option><option value="room">Room</option></select></label>
        <label>Amenity<select value={filters.amenity} onChange={e => setFilters({ ...filters, amenity: e.target.value })}><option value="">Any</option>{amenities.map(item => <option value={item.slug} key={item.id}>{item.name}</option>)}</select></label>
        <label>Sort by<select value={nearby ? "distance" : filters.ordering} onChange={e => setFilters({ ...filters, ordering: e.target.value })} disabled={Boolean(nearby)}><option value="-created_at">Newest</option><option value="monthly_rent">Price: low to high</option><option value="-monthly_rent">Price: high to low</option><option value="bedrooms">Bedrooms</option><option value="distance" disabled={!nearby}>Nearest first (use Homes near me)</option></select></label>
        <button className="button search-button" type="submit" disabled={loading}>{loading ? "Searching…" : "Find homes"}</button>
      </form>
    </section>
    <section className="results-section"><div className="section-heading"><div><p className="eyebrow">Available rentals</p><h2>{nearby ? "Homes around you" : searched ? "Homes for you" : "Explore homes"}</h2></div><div className="results-tools"><span className="muted">{units.length} {units.length === 1 ? "home" : "homes"} shown</span>{nearby && <button className="button-secondary" type="button" onClick={() => setMapVisible(value => !value)}>{mapVisible ? "See list" : "See map"}</button>}</div></div>
      {error && <div className={units.length ? "notice" : "empty glass"} role="status">{error}</div>}
      {loading && <div className="listing-grid">{[1,2,3].map(i => <div className="glass skeleton-card" key={i} aria-label="Loading home" />)}</div>}
      {!loading && nearby && mapVisible && <NearbyMap units={units} center={nearby} />}
      {!loading && units.length > 0 && <div className="listing-grid">{units.map(unit => <Link key={unit.id} href={`/listings/${encodeURIComponent(unit.property.city.toLowerCase())}/${encodeURIComponent(unit.property.area.toLowerCase())}/${unit.slug}`} className="glass listing-card">
        {unit.media[0]?.url ? <img className="listing-image" src={unit.media[0].url} alt={unit.media[0].alt_text || `${unit.title} rental home`} /> : <div className="listing-image image-placeholder" aria-hidden="true"><span>Nyumbani</span></div>}
        <div className="listing-card-content"><span className="status">Available</span><p className="muted location">{unit.property.area}, {unit.property.city}{unit.distance_km !== null && unit.distance_km !== undefined ? ` · ${unit.distance_km} km away` : ""}</p><h3>{unit.title}</h3><strong className="price">KSh {unit.monthly_rent.toLocaleString()} <span>/ month</span></strong><p className="muted">{unit.bedrooms === 0 ? "Bedsitter" : `${unit.bedrooms} bedroom${unit.bedrooms === 1 ? "" : "s"}`} · {unit.bathrooms} bath</p></div>
      </Link>)}</div>}
      {!loading && units.length === 0 && !error && <div className="glass empty">Homes will appear here when available. Try searching a neighborhood.</div>}
      {!loading && searched && units.length > 0 && hasMore && <button className="button button-secondary load-more" onClick={() => void search(undefined, page + 1, true)}>Show more homes</button>}
    </section>
    <footer className="site-footer"><span>Nyumbani · Rent with more certainty.</span><div><Link href="/login">List a home</Link><Link href="/login">Sign in</Link></div></footer>
  </main>;
}
