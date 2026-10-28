"use client";

import { useEffect, useState } from "react";
import type { SessionUser } from "./types";

export function currentUser(): SessionUser | null {
  if (typeof window === "undefined" || !localStorage.getItem("rental_access")) return null;
  try { return JSON.parse(localStorage.getItem("rental_user") || "null"); } catch { return null; }
}

export const dashboardFor = (role?: string) => (role === "admin" ? "/admin" : role === "landlord" ? "/landlord" : "/tenant");

/**
 * Client-side routing convenience only. Every API call is authorised by the server;
 * this just sends people to the right dashboard instead of showing them errors.
 */
export function useRequireRole(role: SessionUser["role"]) {
  const [user, setUser] = useState<SessionUser | null>(null);
  useEffect(() => {
    const signedIn = currentUser();
    if (!signedIn) { window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`); return; }
    if (signedIn.role !== role) { window.location.assign(dashboardFor(signedIn.role)); return; }
    setUser(signedIn);
  }, [role]);
  return user;
}

export function useSessionUser() {
  const [user, setUser] = useState<SessionUser | null | undefined>(undefined);
  useEffect(() => { setUser(currentUser()); }, []);
  return user;
}
