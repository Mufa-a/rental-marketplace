"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { dateTime } from "@/lib/format";
import type { TimelineEvent, ViewingRequest } from "@/lib/types";

/** Expandable, audited booking history for one request. */
export default function RequestTimeline({ requestId }: { requestId: number }) {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [open, setOpen] = useState(false);
  async function toggle() {
    setOpen((o) => !o);
    if (!events) {
      const detail = await apiFetch<ViewingRequest>(`/viewings/requests/${requestId}/`, {}, true).catch(() => null);
      setEvents(detail?.timeline ?? []);
    }
  }
  return <div className="timeline-wrap">
    <button type="button" className="linklike" aria-expanded={open} onClick={() => void toggle()}>{open ? "Hide history" : "Show booking history"}</button>
    {open && (events === null ? <p className="muted small">Loading…</p> : <ol className="timeline">
      {events.map((e, i) => <li key={i}><strong>{e.label}</strong>{e.detail && <> — {e.detail}</>}<span className="muted"> · {e.by} · {dateTime(e.at)}</span></li>)}
    </ol>)}
  </div>;
}
