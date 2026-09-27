"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiFetch, signOut } from "@/lib/api";
import SiteHeader from "@/components/SiteHeader";

type Profile = { id: number; phone_number: string; role: string; phone_verified: boolean; first_name: string; last_name: string; email: string };

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!localStorage.getItem("rental_access")) { window.location.assign("/login"); return; }
    apiFetch<Profile>("/auth/me/", {}, true).then(setProfile)
      .catch(error => setMessage(error instanceof Error ? error.message : "We could not load your profile."))
      .finally(() => setLoading(false));
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true); setMessage("");
    try {
      const updated = await apiFetch<Profile>("/auth/me/", { method: "PATCH", body: JSON.stringify({ first_name: form.get("first_name"), last_name: form.get("last_name"), email: form.get("email") }) }, true);
      setProfile(updated); setMessage("Your profile has been saved.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "We could not save your profile. Please retry."); }
    finally { setSaving(false); }
  }

  return <main className="shell" style={{ maxWidth: 760 }}><SiteHeader right={<Link href={profile?.role === "landlord" ? "/landlord" : "/tenant"} className="navlink">Back to dashboard</Link>} /><section className="glass profile-panel"><p className="eyebrow">Account settings</p><h1>Your profile</h1>{loading && <p className="muted">Loading your information…</p>}{message && <p className={message.includes("could not") ? "form-error" : "form-success"} role="status">{message}</p>}{profile && <><div className="profile-identity"><div className="avatar" aria-hidden="true">{profile.first_name?.[0] || "N"}</div><div><strong>{profile.phone_number}</strong><p className="muted">{profile.role === "landlord" ? "Landlord" : "Tenant"} account · {profile.phone_verified ? "Phone verified" : "Phone not verified"}</p></div></div><form className="profile-form" onSubmit={save}><label>First name<input name="first_name" maxLength={150} defaultValue={profile.first_name} autoComplete="given-name" /></label><label>Last name<input name="last_name" maxLength={150} defaultValue={profile.last_name} autoComplete="family-name" /></label><label>Email address<input name="email" type="email" maxLength={254} defaultValue={profile.email} autoComplete="email" /></label><label>Phone number<input value={profile.phone_number} disabled /></label><button type="submit" disabled={saving}>{saving ? "Saving…" : "Save profile"}</button></form></>}</section><button className="button-secondary signout-link" onClick={signOut}>Sign out</button></main>;
}
