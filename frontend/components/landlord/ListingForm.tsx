"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/api";
import { UNIT_TYPES } from "@/lib/format";
import { photoProblem, uploadPhotos } from "@/lib/uploads";
import type { Amenity } from "@/lib/types";
import type { OwnProperty, OwnUnit } from "./types";

type Props = {
  properties: OwnProperty[]; amenities: Amenity[]; unit?: OwnUnit; defaultPropertyId?: number;
  onDone: (message: string) => void; onCancel: () => void;
};

const num = (form: FormData, key: string) => (form.get(key) === "" || form.get(key) == null ? null : Number(form.get(key)));

/** Create a new home (optionally a new building) or edit an existing unit. */
export default function ListingForm({ properties, amenities, unit, defaultPropertyId, onDone, onCancel }: Props) {
  const [propertyChoice, setPropertyChoice] = useState(unit ? String(unit.property_id) : defaultPropertyId ? String(defaultPropertyId) : properties.length ? String(properties[0].id) : "new");
  const [coords, setCoords] = useState({ latitude: "", longitude: "" });
  const [chosen, setChosen] = useState<Set<number>>(new Set(unit?.amenities ?? []));
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");

  function locate() {
    if (!navigator.geolocation) { setError("Location is unavailable in this browser. Enter coordinates instead."); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => setCoords({ latitude: p.coords.latitude.toFixed(6), longitude: p.coords.longitude.toFixed(6) }),
      () => setError("We could not read your location. Allow location access or enter coordinates."), { enableHighAccuracy: true, timeout: 10000 });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const photos = form.getAll("photos").filter((v): v is File => v instanceof File && v.size > 0);
    const problem = photoProblem(photos);
    if (problem) { setError(problem); return; }
    setBusy(true); setError("");
    try {
      let propertyId = Number(propertyChoice);
      if (!unit && propertyChoice === "new") {
        setProgress("Saving the building…");
        const created = await apiFetch<OwnProperty>("/properties/mine/", { method: "POST", body: JSON.stringify({
          name: form.get("property_name"), address_line: form.get("address"), area: form.get("area"), city: form.get("city"),
          county: form.get("county"), description: form.get("property_description") || "",
          latitude: Number(coords.latitude), longitude: Number(coords.longitude),
        }) }, true);
        propertyId = created.id;
      }
      const payload = {
        title: form.get("title"), unit_type: form.get("unit_type"), monthly_rent: num(form, "rent"), security_deposit: num(form, "deposit") ?? 0,
        bedrooms: num(form, "bedrooms"), bathrooms: form.get("bathrooms"), floor_area_sqm: num(form, "size"), furnishing: form.get("furnishing"),
        available_from: form.get("available_from") || null, description: form.get("description"), amenities: Array.from(chosen),
        ...(unit ? {} : { unit_number: form.get("unit_number"), is_published: form.get("publish") === "on" }),
      };
      setProgress("Saving the listing…");
      const saved = unit
        ? await apiFetch<OwnUnit>(`/properties/units/${unit.id}/`, { method: "PATCH", body: JSON.stringify(payload) }, true)
        : await apiFetch<OwnUnit>(`/properties/${propertyId}/units/`, { method: "POST", body: JSON.stringify(payload) }, true);
      if (photos.length) {
        try { await uploadPhotos(saved.id, String(form.get("title")), photos, (n) => setProgress(`Uploading photos ${n}/${photos.length}…`)); }
        catch (err) { onDone(`Listing saved, but a photo failed: ${err instanceof Error ? err.message : "try again from Edit"}.`); return; }
      }
      onDone(saved.moderation_status === "pending_review"
        ? "Saved. This listing is waiting for a quick review by our team before it appears in search."
        : unit ? "Listing updated." : saved.is_published ? "Your home is live in search." : "Saved as a draft. Publish it when you are ready.");
    } catch (err) { setError(err instanceof Error ? err.message : "We could not save this listing."); }
    finally { setBusy(false); setProgress(""); }
  }

  const newProperty = !unit && propertyChoice === "new";
  return <form onSubmit={submit} className="listing-form" aria-label={unit ? "Edit listing" : "New listing"}>
    {!unit && <fieldset className="form-section form-wide"><legend>Building</legend>
      <label>Which building is this home in?<select value={propertyChoice} onChange={(e) => setPropertyChoice(e.target.value)}>
        {properties.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.area}</option>)}
        <option value="new">+ A new building / property</option>
      </select></label>
      {newProperty && <div className="form-grid">
        <label>Building name<input name="property_name" maxLength={180} required placeholder="Green Apartments" /></label>
        <label>Street address <span className="muted">(private until a viewing is approved)</span><input name="address" maxLength={255} required placeholder="12 Parklands Road" /></label>
        <label>Estate / neighbourhood<input name="area" maxLength={100} required placeholder="Westlands" /></label>
        <label>Town<input name="city" maxLength={100} required defaultValue="Nairobi" /></label>
        <label>County<input name="county" maxLength={100} required defaultValue="Nairobi" /></label>
        <label>About the building <span className="muted">(optional)</span><input name="property_description" maxLength={500} /></label>
        <div className="form-wide"><p className="muted small">The map pin powers &ldquo;homes near me&rdquo;. The public map shows it only approximately (about 100 m).</p>
          <button type="button" className="button-secondary button-small" onClick={locate}>Use my current location (when at the property)</button></div>
        <label>Latitude<input type="number" step="any" min="-90" max="90" required value={coords.latitude} onChange={(e) => setCoords({ ...coords, latitude: e.target.value })} placeholder="-1.2676" /></label>
        <label>Longitude<input type="number" step="any" min="-180" max="180" required value={coords.longitude} onChange={(e) => setCoords({ ...coords, longitude: e.target.value })} placeholder="36.8108" /></label>
      </div>}
    </fieldset>}

    <fieldset className="form-section form-wide"><legend>The home</legend><div className="form-grid">
      {!unit && <label>Unit / door number <span className="muted">(private)</span><input name="unit_number" maxLength={50} required placeholder="A03" /></label>}
      <label className={unit ? "form-wide" : ""}>Listing title<input name="title" minLength={5} maxLength={180} required defaultValue={unit?.title} placeholder="Bright one bedroom near the bypass" /></label>
      <label>Home type<select name="unit_type" defaultValue={unit?.unit_type ?? "apartment"}>{Object.entries(UNIT_TYPES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
      <label>Monthly rent (KSh)<input name="rent" type="number" min="500" step="100" required defaultValue={unit?.monthly_rent} placeholder="26000" /></label>
      <label>Deposit (KSh)<input name="deposit" type="number" min="0" step="100" defaultValue={unit?.security_deposit || ""} placeholder="26000" /></label>
      <label>Bedrooms<input name="bedrooms" type="number" min="0" max="20" required defaultValue={unit?.bedrooms ?? 1} /></label>
      <label>Bathrooms<input name="bathrooms" type="number" step="0.5" min="0.5" max="20" required defaultValue={unit?.bathrooms ?? 1} /></label>
      <label>Size (m²) <span className="muted">(optional)</span><input name="size" type="number" min="5" max="5000" defaultValue={unit?.floor_area_sqm ?? ""} /></label>
      <label>Furnishing<select name="furnishing" defaultValue={unit?.furnishing ?? "unfurnished"}><option value="unfurnished">Unfurnished</option><option value="semi_furnished">Semi-furnished</option><option value="furnished">Furnished</option></select></label>
      <label>Available from <span className="muted">(blank = now)</span><input name="available_from" type="date" defaultValue={unit?.available_from ?? ""} /></label>
      <label className="form-wide">Description<textarea name="description" maxLength={5000} rows={4} defaultValue={unit?.description} placeholder="Rooms, light, water, security, transport. Be accurate — misleading listings are removed." /></label>
    </div></fieldset>

    {amenities.length > 0 && <fieldset className="form-section form-wide check-group"><legend>Amenities</legend>
      {amenities.map((a) => <label key={a.id} className="check"><input type="checkbox" checked={chosen.has(a.id)} onChange={() => setChosen((s) => { const n = new Set(s); if (n.has(a.id)) n.delete(a.id); else n.add(a.id); return n; })} />{a.name}</label>)}
    </fieldset>}

    <label className="form-wide">{unit ? "Add photos" : "Photos"} <span className="muted">(up to 8 at a time; JPEG, PNG or WebP. Location data is removed before upload.)</span>
      <input name="photos" type="file" accept="image/jpeg,image/png,image/webp" multiple /></label>
    {!unit && <label className="check form-wide"><input type="checkbox" name="publish" defaultChecked />Publish now (you can pause it any time)</label>}
    <p className="muted small form-wide">By publishing you confirm the home exists, you may let it, and the details are accurate (see the <a href="/listing-rules" target="_blank">listing rules</a>).</p>
    {error && <p className="notice notice-error form-wide" role="alert">{error}</p>}
    <div className="inline-actions form-wide">
      <button type="submit" disabled={busy}>{busy ? progress || "Saving…" : unit ? "Save changes" : "Save listing"}</button>
      <button type="button" className="button-secondary" onClick={onCancel} disabled={busy}>Cancel</button>
    </div>
  </form>;
}
