"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiFetch, storeSession } from "@/lib/api";
import SiteHeader from "@/components/SiteHeader";
import { LEGAL_VERSION } from "@/lib/legal/config";
import { currentUser, dashboardFor } from "@/lib/session";
import type { SessionUser } from "@/lib/types";

type VerifyResponse = { access?: string; user?: SessionUser; mfa_required?: boolean; mfa_ticket?: string };

/** Only same-site paths are honoured as a post-login destination (no open redirects). */
const safeNext = (value: string | null) => (value && value.startsWith("/") && !value.startsWith("//") ? value : null);

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [phone, setPhone] = useState(""); const [code, setCode] = useState("");
  const [role, setRole] = useState(params.get("role") === "landlord" ? "landlord" : "tenant");
  const [accepted, setAccepted] = useState(false);
  const [requested, setRequested] = useState(false);
  const [message, setMessage] = useState(""); const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [mfaTicket, setMfaTicket] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const signup = params.get("mode") === "signup";

  useEffect(() => { if (currentUser()) router.replace(safeNext(params.get("next")) ?? "/"); }, [params, router]);

  async function requestOtp(event?: FormEvent) {
    event?.preventDefault(); setBusy(true); setFailed(false); setMessage(requested ? "Sending a new code…" : "Sending code…");
    try {
      await apiFetch("/auth/otp/request/", { method: "POST", body: JSON.stringify({ phone_number: phone, role, accept_terms: accepted, policy_version: LEGAL_VERSION }) });
      setRequested(true); setCode("");
      setMessage("We sent a 6-digit code by SMS. It is valid for five minutes; earlier codes stop working.");
    } catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : "We could not send a code. Please try again."); }
    finally { setBusy(false); }
  }

  async function verify(event: FormEvent) {
    event.preventDefault(); setBusy(true); setFailed(false); setMessage("Verifying…");
    try {
      const body = await apiFetch<VerifyResponse>("/auth/otp/verify/", { method: "POST", body: JSON.stringify({ phone_number: phone, code }) });
      if (body.mfa_required && body.mfa_ticket) {
        setMfaTicket(body.mfa_ticket); setMessage("Enter the 6-digit code from your authenticator app."); setBusy(false);
        return;
      }
      finish(body);
    } catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : "We could not verify that code."); setBusy(false); }
  }

  function finish(body: VerifyResponse) {
    if (!body.access || !body.user) throw new Error("Sign-in did not complete. Please try again.");
    storeSession(body.access, body.user);
    router.push(safeNext(params.get("next")) ?? dashboardFor(body.user.role));
  }

  async function verifyMfa(event: FormEvent) {
    event.preventDefault(); setBusy(true); setFailed(false); setMessage("Checking…");
    try {
      finish(await apiFetch<VerifyResponse>("/auth/mfa/verify/", { method: "POST", body: JSON.stringify({ mfa_ticket: mfaTicket, code: mfaCode }) }));
    } catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : "That code did not work."); setBusy(false); }
  }

  if (mfaTicket) {
    return <section className="glass auth-card">
      <p className="eyebrow">Administrator sign-in</p>
      <h1>Authenticator code</h1>
      <p className="muted">Open your authenticator app and enter the current 6-digit code for Nyumbani admin.</p>
      <form onSubmit={verifyMfa} className="field-stack">
        <label>Authenticator code<input autoComplete="one-time-code" inputMode="numeric" required pattern="[0-9]{6}" maxLength={6} autoFocus value={mfaCode} onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" /></label>
        <button type="submit" disabled={busy || mfaCode.length !== 6}>{busy ? "Checking…" : "Sign in"}</button>
      </form>
      {message && <p className={failed ? "notice notice-error" : "muted"} role="status" aria-live="polite">{message}</p>}
    </section>;
  }

  return <section className="glass auth-card">
    <p className="eyebrow">{signup ? "Create your free account" : "Welcome back"}</p>
    <h1>{requested ? "Enter your code" : signup ? "Join Nyumbani" : "Sign in"}</h1>
    <p className="muted">Use your Kenyan mobile number. We send a one-time code by SMS — there is no password to remember.</p>
    {!requested ? <form onSubmit={requestOtp} className="field-stack">
      <label>Phone number<input autoComplete="tel" inputMode="tel" required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712 345 678" /></label>
      <fieldset className="role-choice"><legend>I want to…</legend>
        <label className={`role-option${role === "tenant" ? " is-selected" : ""}`}><input type="radio" name="role" value="tenant" checked={role === "tenant"} onChange={() => setRole("tenant")} /><strong>Find a home</strong><span>Browse free, buy viewing credits when ready</span></label>
        <label className={`role-option${role === "landlord" ? " is-selected" : ""}`}><input type="radio" name="role" value="landlord" checked={role === "landlord"} onChange={() => setRole("landlord")} /><strong>List a home</strong><span>Free to list; success fee only after a rental</span></label>
      </fieldset>
      <p className="muted small">Already have an account? The account type you chose when you signed up is kept.</p>
      <div className="consent-row"><input id="accept-terms" type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} aria-describedby="accept-terms-help" /><label htmlFor="accept-terms">I agree to the <Link href="/terms" target="_blank">Terms</Link> and acknowledge the <Link href="/privacy" target="_blank">Privacy Policy</Link>.<span id="accept-terms-help" className="muted"> Required for new accounts.</span></label></div>
      <button type="submit" disabled={busy}>{busy ? "Sending…" : "Send verification code"}</button>
    </form> : <form onSubmit={verify} className="field-stack">
      <label>6-digit code<input autoComplete="one-time-code" inputMode="numeric" required pattern="[0-9]{6}" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" maxLength={6} autoFocus /></label>
      <button type="submit" disabled={busy || code.length !== 6}>{busy ? "Verifying…" : "Verify and continue"}</button>
      <div className="inline-actions"><button className="button-secondary" type="button" disabled={busy} onClick={() => void requestOtp()}>Send a new code</button><button className="button-secondary" type="button" onClick={() => { setRequested(false); setCode(""); setMessage(""); }}>Change number</button></div>
    </form>}
    {message && <p className={failed ? "notice notice-error" : "muted"} role="status" aria-live="polite">{message}</p>}
  </section>;
}

export default function LoginPage() {
  return <main className="shell narrow"><SiteHeader right={<Link className="navlink" href="/">Back to search</Link>} /><Suspense fallback={<div className="glass auth-card" aria-busy="true" />}><LoginForm /></Suspense></main>;
}
