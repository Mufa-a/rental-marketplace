"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { activeFilterCount, EMPTY_FILTERS, Filters, queryString } from "@/lib/search";
import { plural, UNIT_TYPES } from "@/lib/format";
import type { Amenity, LocationSuggestion, PublicListing, SearchPage } from "@/lib/types";
import ListingCard from "./ListingCard";
import NearbyMap from "./NearbyMap";

const POPULAR = ["Kilimani", "Westlands", "Kileleshwa", "Kasarani", "Ruaka", "Syokimau", "Nyali", "Milimani"];
const ORDER_LABELS: [string, string][] = [["", "Best match / newest"], ["-created_at", "Newest"], ["monthly_rent", "Rent: low to high"], ["-monthly_rent", "Rent: high to low"], ["-bedrooms", "Most bedrooms"]];

const cursorOf = (next: string | null) => {
  if (!next) return null;
  try { return new URL(next).searchParams.get("cursor"); } catch { return null; }
};

type Props = { initial: SearchPage | null; initialFilters: Filters; amenities: Amenity[]; heading?: string; intro: React.ReactNode; heroClassName?: string };

export default function SearchExperience({ initial, initialFilters, amenities, heading, intro, heroClassName = "" }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [applied, setApplied] = useState<Filters>(initialFilters);
  const [results, setResults] = useState<PublicListing[]>(initial?.results ?? []);
  const [count, setCount] = useState<number>(initial?.count ?? 0);
  const [cursor, setCursor] = useState<string | null>(cursorOf(initial?.next ?? null));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(initial ? "" : "We could not load homes right now. Check your connection and try again.");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([]);
  const [nearby, setNearby] = useState<{ latitude: number; longitude: number } | null>(null);
  const [radiusKm, setRadiusKm] = useState("10");
  const [locating, setLocating] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const firstRender = useRef(true);

  const set = (patch: Partial<Filters>) => setFilters((current) => ({ ...current, ...patch }));
  const selectedTypes = useMemo(() => new Set(filters.unit_type.split(",").filter(Boolean)), [filters.unit_type]);
  const selectedAmenities = useMemo(() => new Set(filters.amenities.split(",").filter(Boolean)), [filters.amenities]);
  const toggleIn = (key: "unit_type" | "amenities", value: string) => {
    const current = new Set(filters[key].split(",").filter(Boolean));
    if (current.has(value)) current.delete(value); else current.add(value);
    set({ [key]: Array.from(current).join(",") } as Partial<Filters>);
  };

  // Location suggestions from homes that are actually listed (debounced).
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return; }
    const q = filters.q.trim();
    if (q.length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => {
      apiFetch<LocationSuggestion[]>(`/properties/locations/?q=${encodeURIComponent(q)}`).then(setSuggestions).catch(() => setSuggestions([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [filters.q]);

  async function run(next: Filters, location = nearby, append = false, radius = radiusKm) {
    setLoading(true); setError("");
    const extra: Record<string, string> = {};
    if (location) Object.assign(extra, { latitude: String(location.latitude), longitude: String(location.longitude), radius_km: radius });
    if (append && cursor) extra.cursor = cursor;
    try {
      const data = await apiFetch<SearchPage>(`/properties/search/?${queryString(next, extra)}`);
      setResults((current) => (append ? [...current, ...data.results] : data.results));
      setCount(data.count);
      setCursor(cursorOf(data.next));
      setApplied(next);
      if (!append) {
        const query = queryString(next);
        router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
      }
    } catch (err) {
      if (!append) { setResults([]); setCount(0); }
      setError(err instanceof Error ? err.message : "We could not load homes. Try again.");
    } finally { setLoading(false); }
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    setSheetOpen(false);
    // A suggestion picked from the list becomes precise location filters.
    const match = suggestions.find((s) => `${s.estate}, ${s.town}`.toLowerCase() === filters.q.trim().toLowerCase());
    const next = match ? { ...filters, q: "", county: match.county, town: match.town, estate: match.estate } : filters;
    setFilters(next);
    void run(next);
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function pickArea(estate: string) {
    const next = { ...EMPTY_FILTERS, estate };
    setFilters(next); void run(next);
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function clearAll() {
    setFilters(EMPTY_FILTERS); setNearby(null); setShowMap(false);
    void run(EMPTY_FILTERS, null);
  }

  function findNearby() {
    if (!navigator.geolocation) { setError("Location search is not available in this browser."); return; }
    setLocating(true); setError("");
    navigator.geolocation.getCurrentPosition((position) => {
      const location = { latitude: position.coords.latitude, longitude: position.coords.longitude };
      setNearby(location); setLocating(false);
      void run(filters, location);
    }, () => { setLocating(false); setError("We could not access your location. Allow location access or search by area instead."); },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
  }

  const filtered = activeFilterCount(applied) > 0 || Boolean(nearby);
  const moreCount = activeFilterCount({ ...filters, q: "", min_rent: "", max_rent: "", bedrooms: "" });

  return (
    <>
      <section className={`hero-v2 glass search-hero ${heroClassName}`}>
      <div className="search-intro">{intro}</div>
      <form onSubmit={submit} className="search-panel" role="search" aria-label="Search available rentals">
        <label className="area-field">Where?
          <input value={filters.q} onChange={(e) => set({ q: e.target.value })} list="location-suggestions" autoComplete="off"
                 placeholder="Estate, town or county — e.g. Kilimani" aria-describedby="where-hint" />
          <datalist id="location-suggestions">
            {suggestions.map((s) => <option key={`${s.county}-${s.town}-${s.estate}`} value={`${s.estate}, ${s.town}`}>{`${s.county} · ${plural(s.listings, "home")}`}</option>)}
          </datalist>
          <span id="where-hint" className="sr-only">Suggestions show places that currently have homes listed.</span>
        </label>
        <label>Min. rent<input type="number" inputMode="numeric" min="0" step="500" value={filters.min_rent} onChange={(e) => set({ min_rent: e.target.value })} placeholder="KSh" /></label>
        <label>Max. rent<input type="number" inputMode="numeric" min="0" step="500" value={filters.max_rent} onChange={(e) => set({ max_rent: e.target.value })} placeholder="KSh" /></label>
        <label>Bedrooms<select value={filters.bedrooms} onChange={(e) => set({ bedrooms: e.target.value })}>
          <option value="">Any</option><option value="0">Bedsitter / studio</option>
          {[1, 2, 3, 4].map((n) => <option value={n} key={n}>{n}+ bedrooms</option>)}
        </select></label>
        <button type="button" className="button button-secondary filter-trigger" onClick={() => setSheetOpen(true)} aria-expanded={sheetOpen} aria-controls="more-filters">
          More filters{moreCount ? ` (${moreCount})` : ""}
        </button>
        <button className="button search-button" type="submit" disabled={loading}>{loading ? "Searching…" : "Find homes"}</button>

        {sheetOpen && <div className="sheet-backdrop" onClick={() => setSheetOpen(false)} aria-hidden="true" />}
        <div id="more-filters" className={`filter-sheet${sheetOpen ? " is-open" : ""}`} role="dialog" aria-modal="true" aria-label="More filters" hidden={!sheetOpen}>
          <div className="filter-sheet-head"><strong>More filters</strong><button type="button" className="sheet-close" onClick={() => setSheetOpen(false)} aria-label="Close filters">✕</button></div>
          <div className="filter-grid">
            <label>County<input value={filters.county} onChange={(e) => set({ county: e.target.value })} placeholder="e.g. Kiambu" /></label>
            <label>Town<input value={filters.town} onChange={(e) => set({ town: e.target.value })} placeholder="e.g. Ruaka" /></label>
            <label>Estate / neighbourhood<input value={filters.estate} onChange={(e) => set({ estate: e.target.value })} placeholder="e.g. South B" /></label>
            <label>Bathrooms<select value={filters.bathrooms} onChange={(e) => set({ bathrooms: e.target.value })}>
              <option value="">Any</option>{[1, 2, 3].map((n) => <option key={n} value={n}>{n}+</option>)}
            </select></label>
            <label>Furnishing<select value={filters.furnishing} onChange={(e) => set({ furnishing: e.target.value })}>
              <option value="">Any</option><option value="unfurnished">Unfurnished</option><option value="semi_furnished">Semi-furnished</option><option value="furnished">Furnished</option>
            </select></label>
            <label>Move in by<input type="date" value={filters.move_in_date} onChange={(e) => set({ move_in_date: e.target.value })} /></label>
            <label>Sort by<select value={filters.ordering} onChange={(e) => set({ ordering: e.target.value })}>
              {ORDER_LABELS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
            </select></label>
          </div>
          <fieldset className="check-group"><legend>Home type</legend>
            {Object.entries(UNIT_TYPES).map(([value, text]) => <label key={value} className="check"><input type="checkbox" checked={selectedTypes.has(value)} onChange={() => toggleIn("unit_type", value)} />{text}</label>)}
          </fieldset>
          {amenities.length > 0 && <fieldset className="check-group"><legend>Must have</legend>
            {amenities.map((a) => <label key={a.slug} className="check"><input type="checkbox" checked={selectedAmenities.has(a.slug)} onChange={() => toggleIn("amenities", a.slug)} />{a.name}</label>)}
          </fieldset>}
          <label className="check"><input type="checkbox" checked={filters.verified_only === "true"} onChange={(e) => set({ verified_only: e.target.checked ? "true" : "" })} />Only properties verified by our team</label>
          <div className="sheet-actions">
            <button type="button" className="button-secondary" onClick={() => setFilters({ ...EMPTY_FILTERS, q: filters.q })}>Reset</button>
            <button type="submit" className="button">Show homes</button>
          </div>
        </div>
      </form>

      <div className="area-row" role="group" aria-label="Popular areas">
        <span>Popular</span>
        {POPULAR.map((area) => <button type="button" className="chip" key={area} aria-pressed={applied.estate.toLowerCase() === area.toLowerCase()} onClick={() => pickArea(area)}>{area}</button>)}
        <button type="button" className="chip chip-accent" onClick={findNearby} disabled={locating}>{locating ? "Locating…" : "◎ Near me"}</button>
      </div>
      </section>

      <section className="results-section" id="results" aria-live="polite" aria-busy={loading}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Available rentals</p>
            <h2>{heading ?? (nearby ? "Homes around you" : filtered ? "Matching homes" : "Latest homes")}</h2>
          </div>
          <div className="results-tools">
            <span className="muted">{loading ? "Searching…" : plural(count, "home")}</span>
            {nearby && <>
              <select aria-label="Search radius" value={radiusKm} onChange={(e) => { setRadiusKm(e.target.value); void run(applied, nearby, false, e.target.value); }}>
                {["5", "10", "25", "50"].map((km) => <option key={km} value={km}>Within {km} km</option>)}
              </select>
              <button className="button-secondary button-small" type="button" onClick={() => setShowMap((v) => !v)}>{showMap ? "List" : "Map"}</button>
              <button className="button-secondary button-small" type="button" onClick={() => { setNearby(null); void run(applied, null); }}>Clear location</button>
            </>}
            {filtered && <button className="button-secondary button-small" type="button" onClick={clearAll}>Clear all</button>}
          </div>
        </div>
        {error && <div className="notice notice-error" role="alert">{error} <button type="button" className="button-secondary button-small" onClick={() => void run(applied)}>Try again</button></div>}
        {nearby && showMap && <NearbyMap units={results} center={nearby} />}
        {loading && results.length === 0 && <div className="listing-grid">{[1, 2, 3].map((i) => <div className="glass skeleton-card" key={i} aria-hidden="true" />)}</div>}
        {results.length > 0 && <div className={`listing-grid${loading ? " is-refreshing" : ""}`}>{results.map((unit, index) => <ListingCard key={unit.id} listing={unit} priority={index < 3} />)}</div>}
        {!loading && !error && results.length === 0 && (
          <div className="glass empty empty-state">
            <h3>{filtered ? "No homes match those filters" : "No homes listed yet"}</h3>
            <p>{filtered ? "Try a nearby estate, a wider rent range or fewer must-haves." : "New rentals appear here as landlords publish them."}</p>
            {filtered && <button type="button" className="button button-secondary" onClick={clearAll}>Clear filters</button>}
          </div>
        )}
        {cursor && results.length > 0 && <button className="button button-secondary load-more" type="button" disabled={loading} onClick={() => void run(applied, nearby, true)}>{loading ? "Loading…" : `Show more homes (${results.length} of ${count})`}</button>}
      </section>
    </>
  );
}
