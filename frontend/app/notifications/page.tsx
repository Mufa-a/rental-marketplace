"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { relative } from "@/lib/format";
import { currentUser } from "@/lib/session";
import type { Notification } from "@/lib/types";
import SiteHeader from "@/components/SiteHeader";

type Inbox = { results: Notification[]; next: string | null; unread: number };

export default function NotificationsPage() {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => apiFetch<Inbox>("/notifications/", {}, true).then(setInbox).catch((e) => setError(e instanceof Error ? e.message : "Could not load notifications.")), []);
  useEffect(() => {
    if (!currentUser()) { window.location.assign("/login?next=/notifications"); return; }
    void load();
  }, [load]);

  async function markAll() { await apiFetch("/notifications/read/", { method: "POST", body: "{}" }, true); void load(); }
  async function open(item: Notification) { if (!item.read) await apiFetch("/notifications/read/", { method: "POST", body: JSON.stringify({ ids: [item.id] }) }, true).catch(() => undefined); }

  return <main className="shell narrow-wide">
    <SiteHeader />
    <section className="dashboard-intro"><div><p className="eyebrow">Updates</p><h1>Notifications</h1></div>
      {inbox && inbox.unread > 0 && <button className="button-secondary" onClick={() => void markAll()}>Mark all as read</button>}</section>
    {error && <p className="notice notice-error">{error}</p>}
    {inbox === null && !error && <div className="glass skeleton-card short" aria-busy="true" />}
    {inbox?.results.length === 0 && <div className="glass empty"><h3>You&apos;re all caught up</h3><p>Viewing replies, reminders and payment confirmations appear here.</p></div>}
    <ul className="plain-list notification-list">{inbox?.results.map((n) => <li key={n.id} className={`glass notification${n.read ? "" : " is-unread"}`}>
      {n.link ? <Link href={n.link} onClick={() => void open(n)}><strong>{n.title || "Update"}</strong><p>{n.message}</p></Link> : <div><strong>{n.title || "Update"}</strong><p>{n.message}</p></div>}
      <span className="muted small">{relative(n.created_at)}</span>
    </li>)}</ul>
  </main>;
}
