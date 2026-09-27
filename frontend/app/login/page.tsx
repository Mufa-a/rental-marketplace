"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import SiteHeader from "@/components/SiteHeader";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState(""); const [code, setCode] = useState("");
  const [role, setRole] = useState("tenant"); const [requested, setRequested] = useState(false); const [message, setMessage] = useState("");
  async function requestOtp(event: FormEvent) {
    event.preventDefault(); setMessage("Sending code…");
    try {
      await apiFetch("/auth/otp/request/", { method: "POST", body: JSON.stringify({ phone_number: phone, role }) });
      setMessage("We sent a one-time code to your phone. It is valid for five minutes."); setRequested(true);
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not send a code. Please try again."); }
  }
  async function verify(event: FormEvent) {
    event.preventDefault(); setMessage("Verifying…");
    let body;
    try { body = await apiFetch<any>("/auth/otp/verify/", { method: "POST", body: JSON.stringify({ phone_number: phone, code }) }); }
    catch (error) { setMessage(error instanceof Error ? error.message : "We could not verify that code."); return; }
    localStorage.setItem("rental_access", body.access); localStorage.setItem("rental_refresh", body.refresh); localStorage.setItem("rental_user", JSON.stringify(body.user));
    router.push(body.user.role === "admin" ? "/admin" : body.user.role === "landlord" ? "/landlord" : "/tenant");
  }
  async function resendOtp() {
    setMessage("Sending a new code…");
    try {
      await apiFetch("/auth/otp/request/", { method: "POST", body: JSON.stringify({ phone_number: phone, role }) });
      setMessage("A new code has been sent. Previous codes are no longer valid."); setCode("");
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not send a new code."); }
  }
  return <main className="shell" style={{ maxWidth: 560 }}><SiteHeader right={<Link className="navlink" href="/">Back to search</Link>} /><section className="glass" style={{ padding: "clamp(24px,6vw,38px)" }}><p className="eyebrow">Your next step starts here</p><h1>{requested ? "Check your messages" : "Sign in or create an account"}</h1><p className="muted">Use your Kenyan phone number. We will send a one-time verification code.</p>{!requested ? <form onSubmit={requestOtp} className="field-stack" style={{ marginTop: 25 }}><label>Phone number<input autoComplete="tel" inputMode="tel" required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712345678" /></label><label>I am looking to…<select value={role} onChange={(e) => setRole(e.target.value)}><option value="tenant">Find a rental</option><option value="landlord">List a rental</option></select></label><button type="submit">Send verification code</button></form> : <form onSubmit={verify} className="field-stack" style={{ marginTop: 25 }}><label>6-digit code<input autoComplete="one-time-code" inputMode="numeric" required pattern="[0-9]{6}" value={code} onChange={(e) => setCode(e.target.value)} placeholder="000000" maxLength={6} /></label><button type="submit">Verify and continue</button><div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}><button className="button-secondary" type="button" onClick={resendOtp}>Send a new code</button><button className="button-secondary" type="button" onClick={() => { setRequested(false); setCode(""); setMessage(""); }}>Change phone number</button></div></form>}<p className="muted" role="status" aria-live="polite" style={{ marginBottom: 0 }}>{message}</p></section></main>;
}
