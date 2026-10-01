"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/api";

const REASONS: [string, string][] = [
  ["fraudulent_listing", "Fraudulent or fake listing"],
  ["misleading_information", "Misleading price, photos or details"],
  ["suspicious_payment_request", "Asked to pay outside the platform or in advance"],
  ["inappropriate_content", "Inappropriate content"],
  ["harassment", "Harassment or abuse"],
  ["other", "Something else"],
];

export default function ReportListingButton({ unitId }: { unitId: number }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("fraudulent_listing");
  const [detail, setDetail] = useState("");
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  function begin() {
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    setOpen(true);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setMessage(""); setFailed(false);
    try {
      await apiFetch("/trust/reports/", { method: "POST", body: JSON.stringify({ listing_id: unitId, reason, detail }) }, true);
      setSent(true); setOpen(false); setMessage("Thank you. Our team will review your report.");
    } catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : "We could not send your report. Please try again."); }
    finally { setBusy(false); }
  }

  return (
    <div className="report-listing">
      {!open && !sent && <button type="button" className="button-secondary button-small" onClick={begin}>Report this listing</button>}
      {open && (
        <form className="field-stack glass report-form" onSubmit={submit}>
          <label>What is wrong?<select value={reason} onChange={(e) => setReason(e.target.value)}>{REASONS.map(([value, text]) => <option value={value} key={value}>{text}</option>)}</select></label>
          <label>More detail <span className="muted">(optional)</span><textarea rows={3} maxLength={2000} value={detail} onChange={(e) => setDetail(e.target.value)} /></label>
          <div className="owner-actions"><button type="submit" disabled={busy}>{busy ? "Sending…" : "Send report"}</button><button type="button" className="button-secondary" onClick={() => setOpen(false)} disabled={busy}>Cancel</button></div>
        </form>
      )}
      {message && <p className={failed ? "form-error" : "form-success"} role="status" aria-live="polite">{message}</p>}
    </div>
  );
}
