"use client";

import { useState } from "react";
import { apiFetch, downloadFile } from "@/lib/api";
import { dashboardFor } from "@/lib/session";
import type { SessionUser } from "@/lib/types";

/** Personal data download and switching between finding and listing homes. */
export default function AccountToolsPanel({ role }: { role: string }) {
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const target = role === "landlord" ? "tenant" : "landlord";

  async function exportData() {
    setBusy(true); setMessage(null);
    try { await downloadFile("/auth/me/export/", `nyumbani-my-data-${new Date().toISOString().slice(0, 10)}.json`); setMessage({ text: "Your data file has been downloaded." }); }
    catch (error) { setMessage({ text: error instanceof Error ? error.message : "The download failed.", error: true }); }
    finally { setBusy(false); }
  }

  async function switchRole() {
    if (!window.confirm(target === "landlord" ? "Switch to a landlord account so you can list homes?" : "Switch to a tenant account so you can request viewings?")) return;
    setBusy(true); setMessage(null);
    try {
      const result = await apiFetch<{ user: SessionUser }>("/auth/me/role/", { method: "POST", body: JSON.stringify({ role: target }) }, true);
      // The access token is unchanged; only the routing profile changes.
      localStorage.setItem("rental_user", JSON.stringify(result.user));
      window.location.assign(dashboardFor(result.user.role));
    } catch (error) { setMessage({ text: error instanceof Error ? error.message : "The switch did not work.", error: true }); setBusy(false); }
  }

  return <section className="glass profile-panel" aria-labelledby="account-tools">
    <h2 id="account-tools">Your data and account type</h2>
    <p className="muted">Download a copy of the personal data we hold about you (JSON). Other people&apos;s details are not included.</p>
    <button type="button" className="button-secondary" disabled={busy} onClick={() => void exportData()}>Download my data</button>
    {role !== "admin" && <>
      <p className="muted">{role === "landlord" ? "Looking for a home yourself?" : "Want to list a home you own or manage?"} You can switch account type when nothing is in progress.</p>
      <button type="button" className="button-secondary" disabled={busy} onClick={() => void switchRole()}>Switch to a {target} account</button>
    </>}
    {message && <p className={`notice ${message.error ? "notice-error" : "notice-success"}`} role="status">{message.text}</p>}
  </section>;
}
