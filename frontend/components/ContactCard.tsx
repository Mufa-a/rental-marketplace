import type { Contact } from "@/lib/types";
import { phone } from "@/lib/format";

/** Shown only after a landlord approves a viewing; the API returns nothing before that. */
export default function ContactCard({ contact, who }: { contact: Contact; who: "landlord" | "tenant" }) {
  const maps = contact.latitude != null && contact.longitude != null
    ? `https://www.google.com/maps/search/?api=1&query=${contact.latitude},${contact.longitude}` : null;
  return <div className="contact-card">
    <p className="eyebrow">{who === "landlord" ? "Viewing details" : "Tenant contact"}</p>
    {contact.address && <p><strong>{contact.address}</strong><br />{[contact.area, contact.city, contact.county].filter(Boolean).join(", ")}</p>}
    {contact.meeting_note && <p><span className="muted">Meeting note:</span> {contact.meeting_note}</p>}
    <p>{contact.name} · <a href={`tel:${contact.phone}`}>{phone(contact.phone)}</a></p>
    <div className="inline-actions">
      <a className="button button-small" href={`tel:${contact.phone}`}>Call</a>
      {maps && <a className="button-secondary button-small" href={maps} target="_blank" rel="noopener noreferrer">Open in Maps</a>}
    </div>
    {who === "landlord" && <p className="muted small">Never pay a deposit or &ldquo;booking fee&rdquo; before you have seen the home and the landlord&apos;s documents.</p>}
  </div>;
}
