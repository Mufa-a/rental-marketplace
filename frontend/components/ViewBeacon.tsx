"use client";

import { useEffect } from "react";
import { apiFetch } from "@/lib/api";

/** Counts a real page view (one per visitor per listing per few hours, enforced server-side). */
export default function ViewBeacon({ slug }: { slug: string }) {
  useEffect(() => {
    const key = `viewed:${slug}`;
    try { if (sessionStorage.getItem(key)) return; sessionStorage.setItem(key, "1"); } catch { /* storage blocked: still count */ }
    void apiFetch(`/properties/listings/${encodeURIComponent(slug)}/view/`, { method: "POST" }, Boolean(localStorage.getItem("rental_access"))).catch(() => undefined);
  }, [slug]);
  return null;
}
