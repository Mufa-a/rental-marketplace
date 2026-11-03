"use client";

import Link from "next/link";
import { signOut } from "@/lib/api";
import { dashboardFor, useSessionUser } from "@/lib/session";
import NotificationBell from "./NotificationBell";

/** Header links that adapt to who is signed in. Server-side permissions are enforced independently. */
export default function AccountNav({ extra }: { extra?: React.ReactNode }) {
  const user = useSessionUser();
  if (user === undefined) return <span className="nav-placeholder" aria-hidden="true" />;
  if (!user) {
    return <>{extra}<Link className="navlink" href="/login">Sign in</Link><Link className="button button-small" href="/login?mode=signup">Create account</Link></>;
  }
  return (
    <>
      {extra}
      <Link className="navlink" href="/">Browse homes</Link>
      {user.role === "tenant" && <Link className="navlink" href="/saved">Saved</Link>}
      <Link className="navlink" href={dashboardFor(user.role)}>{user.role === "admin" ? "Admin" : "Dashboard"}</Link>
      <Link className="navlink" href="/profile">Profile</Link>
      <NotificationBell />
      <button className="button-secondary button-small" type="button" onClick={() => void signOut()}>Sign out</button>
    </>
  );
}
