"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Saved = { unit: { id: number } };

export default function SaveUnitButton({ unitId }: { unitId: number }) {
  const [saved, setSaved] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!localStorage.getItem("rental_access")) return;
    apiFetch<Saved[]>("/properties/saved/", {}, true)
      .then(items => setSaved(items.some(item => item.unit.id === unitId)))
      .catch(() => undefined);
  }, [unitId]);

  async function toggle() {
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    setBusy(true); setMessage("");
    try {
      if (saved) await apiFetch(`/properties/saved/${unitId}/`, { method: "DELETE" }, true);
      else await apiFetch(`/properties/saved/`, { method: "POST", body: JSON.stringify({ unit_id: unitId }) }, true);
      setSaved(!saved); setMessage(saved ? "Removed from saved homes." : "Saved to your homes.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not update your saved homes."); }
    finally { setBusy(false); }
  }

  return <div className="save-unit"><button className="button-secondary" type="button" onClick={toggle} disabled={busy}>{busy ? "Saving…" : saved ? "Saved home ♥" : "Save this home ♡"}</button><span className="muted" role="status" aria-live="polite">{message}</span></div>;
}
