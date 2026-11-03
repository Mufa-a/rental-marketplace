"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { money, plural } from "@/lib/format";
import { newIdempotencyKey, usePaymentStatus } from "@/lib/payments";
import { currentUser } from "@/lib/session";
import type { Package, Payment, Wallet } from "@/lib/types";
import PaymentStatusNotice from "./PaymentStatusNotice";

/** Buy viewing credits. Shows exactly what a credit does before the tenant pays. */
export default function PackagePicker({ onBalance, compact = false }: { onBalance?: (balance: number) => void; compact?: boolean }) {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [choice, setChoice] = useState<Package | null>(null);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [understood, setUnderstood] = useState(false);

  async function load() {
    const data = await apiFetch<Wallet>("/payments/viewing-credits/", {}, true);
    setWallet(data); onBalance?.(data.balance);
    if (data.pending_payment) payment.track(data.pending_payment);
    return data;
  }
  const payment = usePaymentStatus((settled: Payment) => { if (settled.status === "successful") void load(); });

  useEffect(() => {
    const user = currentUser();
    if (!user) return;
    setPhoneNumber(user.phone_number.replace(/^\+254/, "0"));
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load viewing packages."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function buy() {
    if (!choice) return;
    setBusy(true); setError("");
    try {
      const started = await apiFetch<Payment>("/payments/viewing-credits/", {
        method: "POST", body: JSON.stringify({ package_id: choice.id, phone_number: phoneNumber, idempotency_key: newIdempotencyKey() }),
      }, true);
      payment.track(started);
    } catch (err) { setError(err instanceof Error ? err.message : "We could not start the M-Pesa payment."); }
    finally { setBusy(false); }
  }

  if (!wallet) return error ? <p className="notice notice-error">{error}</p> : null;
  return (
    <section className={`credit-shop${compact ? "" : " glass"}`} aria-labelledby="packages-title">
      <div className="section-heading">
        <div><p className="eyebrow">Viewing packages</p><h2 id="packages-title">{compact ? "Get viewing credits" : "Pay only when you want to view"}</h2></div>
        <span className="status">{plural(wallet.balance, "credit")} available</span>
      </div>
      <ul className="conditions">{wallet.conditions.slice(0, compact ? 3 : 6).map((c) => <li key={c}>{c}</li>)}</ul>
      <div className="bundle-grid" role="radiogroup" aria-label="Choose a package">
        {wallet.packages.map((p) => (
          <button type="button" role="radio" aria-checked={choice?.id === p.id} key={p.id} className={choice?.id === p.id ? "is-selected" : ""} onClick={() => setChoice(p)}>
            <strong>{plural(p.credits, "viewing")}</strong>
            <span>{money(p.price, p.currency)}</span>
            {p.credits > 1 && <small>{money(p.price_per_viewing, p.currency)} each</small>}
          </button>
        ))}
      </div>
      {choice && !payment.payment && (
        <div className="checkout">
          <label>M-Pesa number<input type="tel" inputMode="tel" autoComplete="tel" value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} placeholder="0712345678" /></label>
          <label className="check"><input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
            I understand this buys {plural(choice.credits, "viewing request")} on Nyumbani for {money(choice.price, choice.currency)}. It is not rent or a deposit. <Link href="/viewing-packages" target="_blank">Package terms</Link>
          </label>
          <button type="button" onClick={() => void buy()} disabled={busy || !understood || !phoneNumber.trim()}>{busy ? "Sending prompt…" : `Pay ${money(choice.price, choice.currency)} with M-Pesa`}</button>
          <p className="muted small">You will get an M-Pesa prompt on this phone. Enter your PIN to approve. Credits appear once Safaricom confirms the payment.</p>
        </div>
      )}
      {payment.payment && <>
        <PaymentStatusNotice payment={payment.payment} onRefresh={() => void payment.refresh()} />
        {payment.payment.status !== "pending" && <button type="button" className="button-secondary button-small" onClick={() => { payment.reset(); setChoice(null); setUnderstood(false); }}>Done</button>}
      </>}
      {error && <p className="notice notice-error" role="alert">{error}</p>}
    </section>
  );
}
