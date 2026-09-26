"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiFetch, signOut } from "@/lib/api";
import { stripImageMetadata } from "@/lib/images";
import PropertyLocationEditor from "@/components/PropertyLocationEditor";

type Property = { id: number; name: string; area: string; city: string; latitude: number | null; longitude: number | null };
type Unit = { id: number; property_id: number; title: string; description: string; unit_number: string; slug: string; monthly_rent: number; bedrooms: number; available: boolean; is_published: boolean };
type Listing = { property: Property; units: Unit[] };
type ViewingRequest = { id: number; unit: number; unit_title: string; property_name: string; area: string; monthly_rent: number; note: string; status: string; created_at: string; viewing: { id: number; scheduled_at: string; status: string } | null };
type ReferralFee = { id: number; viewing_id: number; unit_title: string; amount: number; status: string; due_at: string | null };
type UploadTicket = { asset_key: string; upload: { url: string; fields: Record<string, string> } };
const localDateTime = (date: Date) => { date.setMinutes(date.getMinutes() - date.getTimezoneOffset()); return date.toISOString().slice(0, 16); };
const defaultSchedule = () => { const date = new Date(); date.setDate(date.getDate() + 1); date.setHours(10, 0, 0, 0); return localDateTime(date); };
const minimumSchedule = () => { const date = new Date(); date.setSeconds(0, 0); date.setMinutes(date.getMinutes() + 30); return localDateTime(date); };

export default function LandlordDashboard() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [requests, setRequests] = useState<ViewingRequest[]>([]);
  const [fees, setFees] = useState<ReferralFee[]>([]);
  const [paymentPhone, setPaymentPhone] = useState("");
  const [payingFeeId, setPayingFeeId] = useState<number | null>(null);
  const [scheduleTimes, setScheduleTimes] = useState<Record<number, string>>({});
  const [scheduleNotes, setScheduleNotes] = useState<Record<number, string>>({});
  const [showForm, setShowForm] = useState(false);
  const [editingUnitId, setEditingUnitId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [workingRequestId, setWorkingRequestId] = useState<number | null>(null);
  const [propertyCoordinates, setPropertyCoordinates] = useState({ latitude: "", longitude: "" });

  async function load() {
    try {
      const [properties, viewingRequests, referralFees] = await Promise.all([
        apiFetch<Property[]>("/properties/mine/", {}, true),
        apiFetch<ViewingRequest[]>("/viewings/requests/", {}, true),
        apiFetch<ReferralFee[]>("/referrals/mine/", {}, true),
      ]);
      const entries = await Promise.all(properties.map(async property => ({ property, units: await apiFetch<Unit[]>(`/properties/${property.id}/units/`, {}, true) })));
      setListings(entries); setRequests(viewingRequests); setFees(referralFees);
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not load your landlord dashboard."); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    const current = localStorage.getItem("rental_user");
    let role = "";
    try { role = current ? JSON.parse(current).role : ""; } catch { localStorage.removeItem("rental_user"); }
    if (role && role !== "landlord") { window.location.assign(role === "admin" ? "/admin" : "/tenant"); return; }
    try { const currentUser = current ? JSON.parse(current) : null; if (currentUser?.phone_number) setPaymentPhone(currentUser.phone_number); } catch { /* the role check above handles an invalid saved session */ }
    void load();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement);
    const photos = form.getAll("photos").filter((value): value is File => value instanceof File && value.size > 0);
    if (photos.length > 8) { setMessage("Choose up to eight photos for each home."); return; }
    if (photos.some(file => !["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024)) {
      setMessage("Photos must be JPEG, PNG, or WebP files under 10 MB each."); return;
    }
    setSaving(true); setMessage("Creating your listing…");
    try {
      const property = await apiFetch<Property>("/properties/mine/", { method: "POST", body: JSON.stringify({ name: form.get("property_name"), address_line: form.get("address"), area: form.get("area"), city: form.get("city"), county: form.get("county"), description: form.get("property_description"), latitude: Number(propertyCoordinates.latitude), longitude: Number(propertyCoordinates.longitude) }) }, true);
      let unit: Unit;
      try {
        unit = await apiFetch<Unit>(`/properties/${property.id}/units/`, { method: "POST", body: JSON.stringify({ unit_number: form.get("unit_number"), title: form.get("title"), unit_type: form.get("unit_type"), monthly_rent: Number(form.get("rent")), bedrooms: Number(form.get("bedrooms")), bathrooms: form.get("bathrooms"), description: form.get("description"), is_published: true }) }, true);
      } catch (error) {
        setMessage(`Property saved, but the unit could not be published: ${error instanceof Error ? error.message : "Please try again."}`);
        await load(); return;
      }
      let photoUploadFailed = false;
      for (const photo of photos) {
        try {
          const cleanPhoto = await stripImageMetadata(photo);
          const ticket = await apiFetch<UploadTicket>(`/properties/units/${unit.id}/media/presign/`, { method: "POST", body: JSON.stringify({ filename: cleanPhoto.name, content_type: cleanPhoto.type }) }, true);
          const uploadData = new FormData();
          Object.entries(ticket.upload.fields).forEach(([key, value]) => uploadData.append(key, value));
          uploadData.append("file", cleanPhoto);
          const uploaded = await fetch(ticket.upload.url, { method: "POST", body: uploadData });
          if (!uploaded.ok) throw new Error("The home is live, but a photo could not be uploaded.");
          await apiFetch(`/properties/units/${unit.id}/media/`, { method: "POST", body: JSON.stringify({ asset_key: ticket.asset_key, alt_text: `${form.get("title")}: ${photo.name}`, media_type: "other" }) }, true);
        } catch {
          photoUploadFailed = true;
          break;
        }
      }
      formElement.reset(); setPropertyCoordinates({ latitude: "", longitude: "" }); setShowForm(false); setMessage(photoUploadFailed ? "Your home is live, but a photo upload failed. You can retry by editing the listing later." : photos.length ? "Your home and photos are now live in search." : "Your home is now available in search."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not create this listing. Please try again."); }
    finally { setSaving(false); }
  }

  async function updateUnit(unit: Unit, updates: Partial<Unit>) {
    try {
      const { available, ...listingUpdates } = updates;
      if (Object.keys(listingUpdates).length) await apiFetch<Unit>(`/properties/units/${unit.id}/`, { method: "PATCH", body: JSON.stringify(listingUpdates) }, true);
      if (available !== undefined) await apiFetch<Unit>(`/properties/units/${unit.id}/availability/`, { method: "POST", body: JSON.stringify({ available }) }, true);
      setMessage("Listing updated."); await load();
    }
    catch (error) { setMessage(error instanceof Error ? error.message : "We could not update this listing."); }
  }

  function locateProperty() {
    if (!navigator.geolocation) { setMessage("Location is unavailable in this browser. Enter the home's coordinates manually."); return; }
    navigator.geolocation.getCurrentPosition(position => setPropertyCoordinates({ latitude: position.coords.latitude.toFixed(6), longitude: position.coords.longitude.toFixed(6) }), () => setMessage("We could not read your location. Allow location access or enter coordinates manually."), { enableHighAccuracy: true, timeout: 10000 });
  }

  async function saveUnitEdits(event: FormEvent<HTMLFormElement>, unitId: number) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch<Unit>(`/properties/units/${unitId}/`, { method: "PATCH", body: JSON.stringify({ title: form.get("title"), monthly_rent: Number(form.get("rent")), bedrooms: Number(form.get("bedrooms")), description: form.get("description") }) }, true);
      setEditingUnitId(null); setMessage("Listing details updated."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not save the listing."); }
  }

  async function deleteUnit(unit: Unit) {
    if (!window.confirm(`Delete “${unit.title}”? This cannot be undone.`)) return;
    try { await apiFetch(`/properties/units/${unit.id}/`, { method: "DELETE" }, true); setMessage("Listing deleted."); await load(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "We could not delete this listing."); }
  }

  async function action(request: ViewingRequest, kind: "approve" | "reject") {
    let body = {};
    if (kind === "approve") {
      const scheduled = scheduleTimes[request.id] || defaultSchedule();
      if (new Date(scheduled).getTime() <= Date.now()) { setMessage("Choose a future viewing time before approving."); return; }
      body = { scheduled_at: new Date(scheduled).toISOString(), meeting_note: scheduleNotes[request.id] ?? "" };
    }
    setWorkingRequestId(request.id);
    try { await apiFetch(`/viewings/requests/${request.id}/${kind}/`, { method: "POST", body: JSON.stringify(body) }, true); setMessage(kind === "approve" ? "Viewing scheduled. The tenant can now see the agreed time." : "Request declined."); await load(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "We could not update the request."); }
    finally { setWorkingRequestId(null); }
  }

  async function updateViewing(viewingId: number, kind: "complete" | "outcome", choice?: string) {
    try {
      const result = await apiFetch<{ payment_status?: string }>(`/viewings/${viewingId}/${kind}/`, { method: "POST", body: JSON.stringify(kind === "outcome" ? { choice } : {}) }, true);
      setMessage(kind === "complete" ? "Viewing marked complete." : choice === "rented" ? result.payment_status === "pending" ? "Rental reported. The unit is off the marketplace and an M-Pesa prompt has been sent to your registered phone." : "Rental reported and the unit is off the marketplace, but M-Pesa could not start. The fee is listed below so you can retry." : "Viewing outcome recorded."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not update the viewing."); }
  }

  async function payReferralFee(feeId: number) {
    setPayingFeeId(feeId);
    try {
      const result = await apiFetch<{ message?: string }>(`/payments/referral-fees/${feeId}/pay/`, { method: "POST", body: JSON.stringify({ phone_number: paymentPhone }) }, true);
      setMessage(result.message ?? "A payment prompt is already pending. Check your phone to complete it.");
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not start the M-Pesa payment."); }
    finally { setPayingFeeId(null); }
  }

  const pending = requests.filter(item => item.status === "pending_landlord");
  const reportsDue = requests.filter(item => item.viewing && (item.viewing.status === "outcome_pending" || (item.viewing.status === "scheduled" && new Date(item.viewing.scheduled_at).getTime() <= Date.now())));
  return <main className="shell"><header className="topnav"><Link href="/" className="brand">Nyumbani</Link><nav className="nav-actions"><Link className="navlink" href="/profile">Profile</Link><button className="button-secondary" onClick={signOut}>Sign out</button></nav></header>
    {reportsDue.length > 0 && <section className="glass activity-card outcome-first"><p className="eyebrow">Action needed first</p><h2>Report the viewing result</h2><p className="muted">If you rented this unit, report it here. We will take it off the marketplace and send an M-Pesa success-fee prompt to your registered phone.</p>{reportsDue.map(item => <div className="outcome-first-row" key={item.viewing!.id}><div><strong>{item.unit_title || `Home #${item.unit}`}</strong><p className="muted">{item.property_name} · KSh {Number(item.monthly_rent).toLocaleString()} / month</p></div><div className="outcome-actions"><button onClick={() => void updateViewing(item.viewing!.id, "outcome", "rented")}>Rented this home</button><button className="button-secondary" onClick={() => void updateViewing(item.viewing!.id, "outcome", "did_not_rent")}>Did not rent</button><button className="button-secondary" onClick={() => void updateViewing(item.viewing!.id, "outcome", "still_deciding")}>Still deciding</button></div></div>)}</section>}
    <section className="dashboard-intro"><p className="eyebrow">Landlord dashboard</p><h1>Manage your homes</h1><p className="muted">Keep your listings current and respond to viewing requests from one place.</p><button onClick={() => setShowForm(value => !value)}>{showForm ? "Close listing form" : "Add a home"}</button></section>
    <section className="dashboard-content"><div className="section-heading"><div><p className="eyebrow">Landlord success fees</p><h2>Referral fees</h2></div></div>{fees.length === 0 && <p className="muted">A fee is created when you report that a viewing converted to a rental, and the M-Pesa prompt is sent automatically.</p>}{fees.map(fee => <article className="glass activity-card" key={fee.id}><div className="activity-heading"><div><span className={`status status-${fee.status}`}>{fee.status}</span><h3>{fee.unit_title}</h3><p className="muted">KSh {fee.amount.toLocaleString()}{fee.due_at ? ` · Due ${new Date(fee.due_at).toLocaleDateString()}` : ""}</p></div>{fee.status === "pending" && <button disabled={payingFeeId === fee.id || !paymentPhone.trim()} onClick={() => void payReferralFee(fee.id)}>{payingFeeId === fee.id ? "Connecting…" : "Pay with M-Pesa"}</button>}</div>{fee.status === "pending" && <label>M-Pesa phone number<input type="tel" inputMode="tel" autoComplete="tel" value={paymentPhone} onChange={event => setPaymentPhone(event.target.value)} placeholder="0712345678" aria-label="M-Pesa phone number" /></label>}</article>)}</section>
    {message && <p className="dashboard-message" role="status" aria-live="polite">{message}</p>}
    {showForm && <section className="glass form-panel"><p className="eyebrow">New rental</p><h2>Property and unit details</h2><form onSubmit={submit} className="listing-form"><label>Property name<input name="property_name" maxLength={180} required placeholder="Green Apartments" /></label><label>Street address<input name="address" maxLength={255} required placeholder="12 Parklands Road" /></label><label>Area<input name="area" maxLength={100} required placeholder="Westlands" /></label><label>City<input name="city" maxLength={100} required defaultValue="Nairobi" /></label><label>County<input name="county" maxLength={100} required defaultValue="Nairobi" /></label><label>Property description<input name="property_description" placeholder="Optional overview" /></label><div className="form-wide"><p className="eyebrow">Map location</p><p className="muted">This pin powers nearby search. Use your phone location only when you are at the property; otherwise enter the property coordinates manually. Public pins are shown approximately.</p><button type="button" className="button-secondary" onClick={locateProperty}>Use my current location</button></div><label>Latitude<input type="number" step="any" min="-90" max="90" required value={propertyCoordinates.latitude} onChange={event => setPropertyCoordinates({ ...propertyCoordinates, latitude: event.target.value })} placeholder="-1.2676" /></label><label>Longitude<input type="number" step="any" min="-180" max="180" required value={propertyCoordinates.longitude} onChange={event => setPropertyCoordinates({ ...propertyCoordinates, longitude: event.target.value })} placeholder="36.8108" /></label><label>Unit number<input name="unit_number" maxLength={50} required placeholder="A03" /></label><label>Listing title<input name="title" maxLength={180} required placeholder="Bright one bedroom apartment" /></label><label>Home type<select name="unit_type"><option value="apartment">Apartment</option><option value="studio">Studio</option><option value="bedsitter">Bedsitter</option><option value="house">House</option><option value="maisonette">Maisonette</option><option value="room">Room</option></select></label><label>Monthly rent (KSh)<input name="rent" type="number" min="1" required placeholder="26000" /></label><label>Bedrooms<input name="bedrooms" type="number" min="0" max="99" defaultValue="1" required /></label><label>Bathrooms<input name="bathrooms" type="number" step="0.5" min="0.5" max="99" defaultValue="1" required /></label><label className="form-wide">Photos <span className="muted">(up to 8; JPEG, PNG, or WebP, 10 MB each)</span><input name="photos" type="file" accept="image/jpeg,image/png,image/webp" multiple /></label><label className="form-wide">About this home<textarea name="description" maxLength={5000} rows={4} placeholder="Describe the rooms, light, and nearby transport." /></label><button type="submit" disabled={saving} className="form-wide">{saving ? "Publishing…" : "Publish home"}</button></form></section>}
    <section className="dashboard-content"><div className="section-heading"><div><p className="eyebrow">Your portfolio</p><h2>Rental homes</h2></div><span className="muted">{listings.reduce((total, item) => total + item.units.length, 0)} units</span></div>
      {loading && <div className="glass empty">Loading your listings…</div>}
      {!loading && listings.length === 0 && <div className="glass empty"><h3>Your homes will show here</h3><p>Add a property and unit to make your first rental searchable.</p><button onClick={() => setShowForm(true)}>Add a home</button></div>}
      <div className="owner-list">{listings.map(({ property, units }) => <section className="glass owner-property" key={property.id}><div className="activity-heading"><div><h3>{property.name}</h3><p className="muted">{property.area}, {property.city}</p></div><span className="status">{units.length} {units.length === 1 ? "unit" : "units"}</span></div><PropertyLocationEditor propertyId={property.id} latitude={property.latitude} longitude={property.longitude} onSaved={() => void load()} />{units.length === 0 && <p className="muted">No units yet. Reopen the listing form to publish a unit.</p>}{units.map(unit => <article className="owner-unit-wrap" key={unit.id}><div className="owner-unit"><div><strong>{unit.title}</strong><p className="muted">Unit {unit.unit_number} · KSh {unit.monthly_rent.toLocaleString()} / month · {unit.bedrooms} bed</p><span className={`status ${unit.is_published && unit.available ? "" : "status-paused"}`}>{unit.is_published && unit.available ? "Visible in search" : "Paused"}</span></div><div className="owner-actions"><button className="button-secondary" onClick={() => setEditingUnitId(editingUnitId === unit.id ? null : unit.id)}>{editingUnitId === unit.id ? "Close edit" : "Edit"}</button><button className="button-secondary" onClick={() => void updateUnit(unit, { is_published: !(unit.is_published && unit.available), available: !(unit.is_published && unit.available) })}>{unit.is_published && unit.available ? "Pause" : "Publish"}</button><button className="button-danger" onClick={() => void deleteUnit(unit)}>Delete</button></div></div>{editingUnitId === unit.id && <form className="unit-edit-form" onSubmit={event => void saveUnitEdits(event, unit.id)}><label>Listing title<input name="title" maxLength={180} required defaultValue={unit.title} /></label><label>Monthly rent (KSh)<input name="rent" type="number" min="1" required defaultValue={unit.monthly_rent} /></label><label>Bedrooms<input name="bedrooms" type="number" min="0" max="99" required defaultValue={unit.bedrooms} /></label><label className="form-wide">Description<textarea name="description" maxLength={5000} rows={3} defaultValue={unit.description} /></label><button className="form-wide" type="submit">Save listing</button></form>}</article>)}</section>)}</div>
    </section>
    <section className="dashboard-content"><div className="section-heading"><div><p className="eyebrow">Responses needed</p><h2>Viewing requests</h2></div><span className="muted">{pending.length} awaiting your reply</span></div>{!loading && pending.length === 0 && <div className="glass empty">New viewing requests will appear here.</div>}{pending.map(item => <article className="glass activity-card request-card" key={item.id}><div className="activity-heading"><div><span className="status">New request</span><h3>{item.unit_title || `Home #${item.unit}`}</h3><p className="muted">{item.property_name}{item.area ? ` · ${item.area}` : ""} · KSh {Number(item.monthly_rent || 0).toLocaleString()} / month</p></div><time className="muted">{new Date(item.created_at).toLocaleDateString()}</time></div><div className="request-message"><span className="eyebrow">Tenant’s message</span><p>{item.note || "The tenant did not add a message."}</p></div><div className="request-schedule"><label>Viewing date and time<input type="datetime-local" min={minimumSchedule()} value={scheduleTimes[item.id] ?? defaultSchedule()} onChange={e => setScheduleTimes({ ...scheduleTimes, [item.id]: e.target.value })} /></label><p className="muted">Suggested time: tomorrow at 10:00. Change it to a time that works for both of you.</p><label>Meeting details <span className="muted">(optional)</span><input maxLength={500} value={scheduleNotes[item.id] ?? ""} onChange={e => setScheduleNotes({ ...scheduleNotes, [item.id]: e.target.value })} placeholder="For example, meet at the main entrance" /></label></div><div className="request-actions"><button disabled={workingRequestId === item.id} onClick={() => void action(item, "approve")}>{workingRequestId === item.id ? "Saving…" : "Approve viewing"}</button><button className="button-secondary" disabled={workingRequestId === item.id} onClick={() => void action(item, "reject")}>Decline request</button></div></article>)}</section>
    <section className="dashboard-content"><div className="section-heading"><div><p className="eyebrow">Your schedule</p><h2>Viewings and outcomes</h2></div></div>{!loading && requests.filter(item => item.viewing).length === 0 && <div className="glass empty">Approved and completed viewings will appear here.</div>}{requests.filter(item => item.viewing).map(item => <article className="glass activity-card" key={item.viewing!.id}><div className="activity-heading"><div><span className="status">{item.viewing ? item.viewing.status.replaceAll("_", " ") : "Scheduled"}</span><h3>Home #{item.unit}</h3></div><time className="muted">{item.viewing && new Date(item.viewing.scheduled_at).toLocaleString()}</time></div>{item.viewing?.status === "scheduled" && <button className="button-secondary" onClick={() => void updateViewing(item.viewing!.id, "complete")}>Mark viewing complete</button>}{item.viewing?.status === "outcome_pending" && <p className="muted">Please submit the result at the top of this page.</p>}</article>)}</section>
  </main>;
}
