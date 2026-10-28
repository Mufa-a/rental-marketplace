"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { date, titleCase } from "@/lib/format";

type Status = {
  verified: boolean; disclaimer: string; privacy: string;
  latest: null | { status: string; legal_name: string; relationship: string; submitted_at: string; reviewed_at: string | null; reviewer_note: string };
};

const DOCS: [string, string, string][] = [
  ["id_front", "ID or passport (photo page / front)", "Required"],
  ["id_back", "ID back", "If your ID has a back"],
  ["ownership_proof", "Proof you own or manage the home", "Title, lease, rates or utility bill"],
  ["authority_letter", "Owner's authority letter", "Required for agents and caretakers"],
];

export default function VerificationPanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const [relationship, setRelationship] = useState("owner");

  const load = () => apiFetch<Status>("/verification/landlord/", {}, true).then(setStatus).catch(() => setStatus(null));
  useEffect(() => { void load(); }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    for (const [key, value] of Array.from(form.entries())) if (value instanceof File && value.size === 0) form.delete(key);
    setBusy(true); setMessage(null);
    try {
      await apiFetch("/verification/landlord/", { method: "POST", body: form }, true);
      setMessage({ text: "Submitted. We will review your documents and notify you." }); await load();
    } catch (error) { setMessage({ text: error instanceof Error ? error.message : "We could not submit your documents.", error: true }); }
    finally { setBusy(false); }
  }

  if (!status) return <div className="glass empty" aria-busy="true">Loading verification…</div>;
  const latest = status.latest;
  const canSubmit = !status.verified && latest?.status !== "pending";
  return <section className="glass form-panel" aria-labelledby="verify-title">
    <p className="eyebrow">Landlord verification</p>
    <h2 id="verify-title">{status.verified ? "You are a verified landlord" : "Get an ID-checked badge"}</h2>
    <p className="muted">{status.disclaimer}</p>
    {latest && <p className={`notice ${latest.status === "verified" ? "notice-success" : latest.status === "pending" ? "notice-info" : "notice-warning"}`}>
      <strong>{titleCase(latest.status)}</strong> — submitted {date(latest.submitted_at)}{latest.reviewed_at ? `, reviewed ${date(latest.reviewed_at)}` : ""}.{latest.reviewer_note && <> {latest.reviewer_note}</>}
    </p>}
    {canSubmit && <form onSubmit={submit} className="listing-form" encType="multipart/form-data">
      <label>Full legal name<input name="legal_name" required maxLength={150} autoComplete="name" /></label>
      <label>Document type<select name="id_type" defaultValue="national_id"><option value="national_id">National ID</option><option value="passport">Passport</option><option value="alien_id">Alien ID</option><option value="company_registration">Company registration</option></select></label>
      <label>Document number <span className="muted">(we keep only the last 4 characters)</span><input name="id_number" required minLength={4} maxLength={30} autoComplete="off" /></label>
      <label>Your relationship to the homes<select name="relationship" value={relationship} onChange={(e) => setRelationship(e.target.value)}>
        <option value="owner">I own them</option><option value="agent">I am an agent authorised by the owner</option><option value="caretaker">I am the caretaker / manager</option><option value="company">A company I represent</option></select></label>
      {relationship !== "owner" && <label className="form-wide">Agency or company name<input name="agency_name" maxLength={150} /></label>}
      {DOCS.map(([name, text, hint]) => <label key={name}>{text} <span className="muted">({hint})</span>
        <input type="file" name={name} accept="image/jpeg,image/png,application/pdf" required={name === "id_front" || (name === "authority_letter" && ["agent", "caretaker"].includes(relationship))} /></label>)}
      <p className="muted small form-wide">{status.privacy} Files: JPEG, PNG or PDF, up to 5 MB each.</p>
      <button type="submit" className="form-wide" disabled={busy}>{busy ? "Uploading…" : "Submit for review"}</button>
    </form>}
    {message && <p className={`notice ${message.error ? "notice-error" : "notice-success"}`} role="status">{message.text}</p>}
  </section>;
}
