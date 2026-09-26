"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Bundle = { credits: number; price: number };
type Wallet = { balance: number; bundles: Bundle[] };

export default function ViewingCreditShop({ onBalance }: { onBalance?: (balance: number) => void } = {}) {
  const [wallet, setWallet] = useState<Wallet>({ balance: 0, bundles: [] });
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function refresh() {
    if (!localStorage.getItem("rental_access")) return;
    try {
      const updated = await apiFetch<Wallet>("/payments/viewing-credits/", {}, true);
      setWallet(updated); onBalance?.(updated.balance);
    }
    catch { /* The tenant can still browse without signing in. */ }
  }

  useEffect(() => { void refresh(); }, []);

  async function buy(bundle: Bundle) {
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    if (!phone.trim()) { setMessage("Enter the phone number that should receive the M-Pesa prompt."); return; }
    setBusy(true); setMessage("");
    try {
      const result = await apiFetch<{ message?: string }>("/payments/viewing-credits/", {
        method: "POST",
        body: JSON.stringify({ credits: bundle.credits, phone_number: phone, idempotency_key: crypto.randomUUID() }),
      }, true);
      setMessage(result.message || "Check your phone and approve the M-Pesa prompt. Credits appear after Safaricom confirms payment.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not start the bundle payment."); }
    finally { setBusy(false); }
  }

  return <section className="credit-shop glass" aria-labelledby="credit-shop-title">
    <div className="section-heading"><div><p className="eyebrow">Viewing bundles</p><h2 id="credit-shop-title">Pay only when you want a viewing</h2></div><span className="status">{wallet.balance} {wallet.balance === 1 ? "credit" : "credits"}</span></div>
    <p className="muted">Browsing stays free. One credit sends one request to a landlord. If a landlord declines, you cancel before approval, or the request expires unanswered, that credit is returned.</p>
    <label>M-Pesa phone number<input type="tel" inputMode="tel" autoComplete="tel" value={phone} onChange={event => setPhone(event.target.value)} placeholder="0712345678" /></label>
    <div className="bundle-grid">{(wallet.bundles.length ? wallet.bundles : [{ credits: 1, price: 50 }, { credits: 3, price: 100 }, { credits: 5, price: 150 }, { credits: 10, price: 250 }]).map(bundle => <button type="button" key={bundle.credits} disabled={busy} onClick={() => void buy(bundle)}><strong>{bundle.credits} {bundle.credits === 1 ? "home" : "homes"}</strong><span>KSh {bundle.price}</span></button>)}</div>
    <div className="credit-actions"><button type="button" className="button-secondary" onClick={() => void refresh()}>Refresh credits</button><p className="muted" role="status" aria-live="polite">{busy ? "Sending payment prompt…" : message}</p></div>
  </section>;
}
