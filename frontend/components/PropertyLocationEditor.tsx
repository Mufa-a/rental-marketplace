"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";

export default function PropertyLocationEditor({ propertyId, latitude, longitude, onSaved }: { propertyId: number; latitude: number | null; longitude: number | null; onSaved?: () => void }) {
  const [open, setOpen] = useState(false);
  const [lat, setLat] = useState(latitude == null ? "" : String(latitude));
  const [lon, setLon] = useState(longitude == null ? "" : String(longitude));
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  function useCurrentLocation() {
    if (!navigator.geolocation) { setMessage("Location is unavailable. Enter coordinates manually."); return; }
    navigator.geolocation.getCurrentPosition(position => { setLat(position.coords.latitude.toFixed(6)); setLon(position.coords.longitude.toFixed(6)); }, () => setMessage("Location access failed. Enter coordinates manually."), { enableHighAccuracy: true, timeout: 10000 });
  }
  async function save() {
    if (!lat || !lon) { setMessage("Enter both latitude and longitude."); return; }
    setSaving(true); setMessage("");
    try { await apiFetch(`/properties/${propertyId}/`, { method: "PATCH", body: JSON.stringify({ latitude: Number(lat), longitude: Number(lon) }) }, true); setMessage("Map location saved."); setOpen(false); onSaved?.(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not save this map location."); }
    finally { setSaving(false); }
  }
  return <div className="property-location-editor"><button type="button" className="button-secondary" onClick={() => setOpen(value => !value)}>{open ? "Close map location" : latitude == null || longitude == null ? "Add map location" : "Update map location"}</button>{open && <div className="coordinate-editor"><p className="muted">Use your device location only if you are at this home. Public map pins are approximate.</p><button type="button" className="button-secondary" onClick={useCurrentLocation}>Use current location</button><label>Latitude<input type="number" step="any" value={lat} onChange={event => setLat(event.target.value)} placeholder="-1.2676" /></label><label>Longitude<input type="number" step="any" value={lon} onChange={event => setLon(event.target.value)} placeholder="36.8108" /></label><button type="button" onClick={() => void save()} disabled={saving}>{saving ? "Saving…" : "Save map location"}</button></div>}<p className="muted" role="status">{message}</p></div>;
}
