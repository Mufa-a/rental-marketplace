"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { currentUser } from "@/lib/session";
import PackagePicker from "./PackagePicker";

const SLOTS = ["Weekday morning", "Weekday afternoon", "Weekday evening", "Saturday", "Sunday"];

export default function ViewingRequestButton({ unitId }: { unitId: number }) {
  const pathname = usePathname();
  const [role, setRole] = useState<string | null | undefined>(undefined);
  const [note, setNote] = useState("");
  const [times, setTimes] = useState<string[]>([]);
  const [balance, setBalance] = useState<number | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => { setRole(currentUser()?.role ?? null); }, []);

  async function requestViewing() {
    setSending(true); setMessage("");
    try {
      await apiFetch("/viewings/requests/", { method: "POST", body: JSON.stringify({ unit: unitId, preferred_times: times, note }) }, true);
      setSent(true); setBalance((b) => (b == null ? b : b - 1));
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not send your request. Please try again."); }
    finally { setSending(false); }
  }

  if (role === undefined) return <div className="skeleton-line" aria-hidden="true" />;
  if (role === null) {
    return <div className="viewing-request">
      <p>Sign in or create a free account to request a viewing. Browsing and saving homes is free.</p>
      <Link className="button" href={`/login?next=${encodeURIComponent(pathname)}`}>Sign in to request a viewing</Link>
    </div>;
  }
  if (role !== "tenant") return <p className="muted">Viewing requests are made from tenant accounts.</p>;
  if (sent) {
    return <div className="notice notice-success" role="status">
      <strong>Request sent.</strong>
      <p>The landlord will approve with a time or decline. One credit is set aside and is only used if they approve. We will notify you by SMS and in your dashboard.</p>
      <Link className="button button-small" href="/tenant">Track your request</Link>
    </div>;
  }
  return <div className="viewing-request">
    <ol className="steps-inline">
      <li>Send a request (uses 1 credit only if approved)</li>
      <li>Landlord approves a time</li>
      <li>You get the address and contact</li>
    </ol>
    <fieldset className="check-group"><legend>When suits you? <span className="muted">(optional)</span></legend>
      {SLOTS.map((slot) => <label key={slot} className="check"><input type="checkbox" checked={times.includes(slot)} onChange={() => setTimes((t) => t.includes(slot) ? t.filter((x) => x !== slot) : [...t, slot])} />{slot}</label>)}
    </fieldset>
    <label htmlFor="viewing-note">Message to landlord <span className="muted">(optional)</span></label>
    <textarea id="viewing-note" rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="When do you hope to move in? Any questions?" />
    <p className="muted small">Don&apos;t share bank details or send money. The landlord sees your phone number only after approving.</p>
    <button type="button" onClick={() => void requestViewing()} disabled={sending || !balance}>{sending ? "Sending request…" : balance ? "Request a viewing" : "Buy a package to request"}</button>
    {message && <p className="notice notice-error" role="alert">{message}</p>}
    {balance === 0 && <p className="muted small">You have no viewing credits yet. Choose a package below.</p>}
    <PackagePicker compact onBalance={setBalance} />
  </div>;
}
