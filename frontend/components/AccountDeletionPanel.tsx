"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type DeletionInfo = {
  request: { status: string; requested_at: string; resolved_at: string | null } | null;
  will_happen: string[];
  may_be_retained: string[];
  warnings: string[];
};

/** Secure deletion-request workflow: explains consequences, requires typed confirmation, is reviewed by a person. */
export default function AccountDeletionPanel({ phone }: { phone: string }) {
  const [info, setInfo] = useState<DeletionInfo | null>(null);
  const [open, setOpen] = useState(false);
  const [confirmPhone, setConfirmPhone] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = () => apiFetch<DeletionInfo>("/auth/deletion-request/", {}, true).then(setInfo).catch(() => setInfo(null));
  useEffect(() => { void load(); }, []);

  const pending = info?.request?.status === "pending";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setMessage(""); setFailed(false);
    try {
      await apiFetch("/auth/deletion-request/", { method: "POST", body: JSON.stringify({ confirm_phone: confirmPhone, reason }) }, true);
      setMessage("Your deletion request was sent. An administrator will review it; nothing has been deleted yet. You can cancel it here until it is processed.");
      setOpen(false); setConfirmPhone(""); setReason(""); await load();
    } catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : "We could not send your request. Please try again."); }
    finally { setBusy(false); }
  }
  async function cancel() {
    setBusy(true); setMessage(""); setFailed(false);
    try { await apiFetch("/auth/deletion-request/", { method: "DELETE" }, true); setMessage("Your deletion request was cancelled."); await load(); }
    catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : "We could not cancel your request."); }
    finally { setBusy(false); }
  }

  return (
    <section className="glass profile-panel danger-zone" aria-labelledby="delete-title">
      <p className="eyebrow">Your data</p>
      <h2 id="delete-title">Delete your account</h2>
      {pending ? (
        <>
          <p className="muted">You asked to delete your account on {new Date(info!.request!.requested_at).toLocaleDateString()}. It is waiting for an administrator to review it. Nothing has been deleted yet.</p>
          <button className="button-secondary" type="button" onClick={cancel} disabled={busy}>Cancel my request</button>
        </>
      ) : !open ? (
        <>
          <p className="muted">You can ask us to delete your account and personal information. A person reviews every request, so it is not instant.</p>
          <button className="button-secondary" type="button" onClick={() => setOpen(true)}>Request account deletion…</button>
        </>
      ) : (
        <form className="field-stack" onSubmit={submit}>
          <div><strong>What will happen</strong><ul className="plain-list">{info?.will_happen.map((line) => <li key={line}>{line}</li>)}</ul></div>
          <div><strong>What we may need to keep</strong><ul className="plain-list">{info?.may_be_retained.map((line) => <li key={line}>{line}</li>)}</ul></div>
          {info && info.warnings.length > 0 && <div className="notice" role="alert"><strong>Before you continue</strong><ul className="plain-list">{info.warnings.map((line) => <li key={line}>{line}</li>)}</ul></div>}
          <label>Why are you leaving? <span className="muted">(optional)</span><textarea rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <label>To confirm, type your phone number ({phone})<input required inputMode="tel" autoComplete="off" value={confirmPhone} onChange={(e) => setConfirmPhone(e.target.value)} placeholder={phone} /></label>
          <div className="owner-actions"><button className="button-danger" type="submit" disabled={busy || !confirmPhone.trim()}>{busy ? "Sending…" : "Send deletion request"}</button><button className="button-secondary" type="button" onClick={() => setOpen(false)} disabled={busy}>Keep my account</button></div>
        </form>
      )}
      {message && <p className={failed ? "form-error" : "form-success"} role="status" aria-live="polite">{message}</p>}
    </section>
  );
}
