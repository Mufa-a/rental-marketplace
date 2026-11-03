"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export default function NotificationBell() {
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    let alive = true;
    const load = () => apiFetch<{ unread: number }>("/notifications/unread-count/", {}, true)
      .then((data) => { if (alive) setUnread(data.unread); }).catch(() => undefined);
    void load();
    const timer = setInterval(() => { if (document.visibilityState === "visible") void load(); }, 60_000);
    return () => { alive = false; clearInterval(timer); };
  }, []);
  return (
    <Link href="/notifications" className="bell" aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
        <path d="M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9" /><path d="M10 20a2 2 0 0 0 4 0" />
      </svg>
      {unread > 0 && <span className="bell-count" aria-hidden="true">{unread > 99 ? "99+" : unread}</span>}
    </Link>
  );
}
