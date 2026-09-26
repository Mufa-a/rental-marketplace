"use client";

import { useEffect, useRef } from "react";

type MapUnit = { id: number; slug: string; title: string; monthly_rent: number; distance_km: number | null; property: { area: string; city: string; latitude?: number; longitude?: number } };

declare global { interface Window { L?: any } }

let leafletLoader: Promise<void> | null = null;
const escapeHTML = (value: string) => value.replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" } as Record<string, string>)[character]);
function loadLeaflet() {
  if (window.L) return Promise.resolve();
  if (leafletLoader) return leafletLoader;
  leafletLoader = new Promise<void>((resolve, reject) => {
    const css = document.createElement("link"); css.rel = "stylesheet"; css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    css.integrity = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="; css.crossOrigin = ""; document.head.appendChild(css);
    const script = document.createElement("script"); script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.integrity = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="; script.crossOrigin = "";
    script.onload = () => resolve(); script.onerror = () => reject(new Error("Map library failed to load.")); document.head.appendChild(script);
  });
  return leafletLoader;
}

export default function NearbyMap({ units, center }: { units: MapUnit[]; center: { latitude: number; longitude: number } }) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<any>(null);
  useEffect(() => {
    let cancelled = false;
    void loadLeaflet().then(() => {
      if (cancelled || !element.current || !window.L) return;
      const L = window.L;
      if (map.current) { map.current.remove(); map.current = null; }
      const current = L.map(element.current).setView([center.latitude, center.longitude], 13);
      const key = process.env.NEXT_PUBLIC_MAPTILER_KEY;
      const tiles = key
        ? `https://api.maptiler.com/maps/streets-v4/{z}/{x}/{y}.png?key=${encodeURIComponent(key)}`
        : "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
      L.tileLayer(tiles, { maxZoom: 19, tileSize: key ? 512 : 256, zoomOffset: key ? -1 : 0, attribution: key ? "&copy; <a href=\"https://www.maptiler.com/copyright/\">MapTiler</a> &copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap contributors</a>" : "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap contributors</a>" }).addTo(current);
      L.circleMarker([center.latitude, center.longitude], { radius: 7, color: "#fff", weight: 3, fillColor: "#218c72", fillOpacity: 1 }).bindPopup("Your approximate search center").addTo(current);
      units.forEach(unit => {
        const { latitude, longitude } = unit.property;
        if (latitude == null || longitude == null) return;
        const marker = L.circleMarker([latitude, longitude], { radius: 9, color: "#17242b", weight: 2, fillColor: "#f5bd68", fillOpacity: 1 }).addTo(current);
        const city = encodeURIComponent(unit.property.city.toLowerCase());
        const area = encodeURIComponent(unit.property.area.toLowerCase());
        const slug = encodeURIComponent(unit.slug);
        marker.bindPopup(`<strong>${escapeHTML(unit.title)}</strong><br>KSh ${unit.monthly_rent.toLocaleString()} / month<br>${escapeHTML(unit.property.area)}, ${escapeHTML(unit.property.city)}${unit.distance_km != null ? `<br>${unit.distance_km} km away` : ""}<br><a href="/listings/${city}/${area}/${slug}">See this home</a>`);
      });
      map.current = current;
    }).catch(() => { if (element.current) element.current.textContent = "The map could not load. Nearby homes are still listed below."; });
    return () => { cancelled = true; if (map.current) { map.current.remove(); map.current = null; } };
  }, [units, center]);
  return <div className="nearby-map" ref={element} role="region" aria-label="Map of nearby available rental homes" />;
}
