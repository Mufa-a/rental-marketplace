"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import ViewingCreditShop from "@/components/ViewingCreditShop";

export default function ViewingRequestButton({ unitId }: { unitId: number }) {
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [balance, setBalance] = useState<number | null>(null);

  useEffect(() => {
    if (localStorage.getItem("rental_access")) {
      apiFetch<{ balance: number }>("/payments/viewing-credits/", {}, true).then(wallet => setBalance(wallet.balance)).catch(() => setBalance(0));
    }
  }, []);

  async function requestViewing() {
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    if (balance === null) { setMessage("Choose a viewing bundle below before requesting this home."); return; }
    if (balance === 0) { setMessage("Choose a viewing bundle below before requesting this home."); return; }
    setSending(true); setMessage("");
    try {
      await apiFetch("/viewings/requests/", { method: "POST", body: JSON.stringify({ unit: unitId, preferred_times: [], note }) }, true);
      setSent(true); setMessage("Your viewing request is with the landlord. Track it in your dashboard.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not send your request. Please try again."); }
    finally { setSending(false); }
  }

  return <div className="viewing-request"><label htmlFor="viewing-note">Message to landlord <span className="muted">(optional)</span></label><textarea id="viewing-note" rows={3} maxLength={500} value={note} onChange={e => setNote(e.target.value)} placeholder="Tell the landlord when you hope to move in or ask a question." /><p className="muted">One viewing credit is used when the landlord approves. Your credit returns if they decline, you cancel before approval, or the request expires unanswered.</p><button onClick={requestViewing} disabled={sending || sent || balance === 0}>{sending ? "Sending request…" : sent ? "Request sent" : "Request a viewing"}</button><p className="muted" role="status" aria-live="polite">{message}</p>{sent && <Link className="navlink" href="/tenant">Go to your dashboard</Link>}<ViewingCreditShop onBalance={setBalance} /></div>;
}
