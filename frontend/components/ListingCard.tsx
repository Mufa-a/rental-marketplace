import Link from "next/link";
import type { PublicListing } from "@/lib/types";
import { bathroomsLabel, bedroomsLabel, FURNISHING, money, UNIT_TYPES } from "@/lib/format";
import VerificationBadge from "./VerificationBadge";

function HomeGlyph() {
  return <svg viewBox="0 0 64 64" width="48" height="48" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><path d="M8 30 32 10l24 20" /><path d="M14 27v27h36V27" /><path d="M27 54V38h10v16" /></svg>;
}

function facts(listing: PublicListing) {
  const type = UNIT_TYPES[listing.unit_type] ?? listing.unit_type;
  const rooms = bedroomsLabel(listing.bedrooms, listing.unit_type);
  // A bedsitter/studio label already names the type.
  return [rooms, bathroomsLabel(listing.bathrooms), ...(rooms === type ? [] : [type]), FURNISHING[listing.furnishing] ?? listing.furnishing];
}

export default function ListingCard({ listing, priority = false }: { listing: PublicListing; priority?: boolean }) {
  const photo = listing.media[0];
  return (
    <Link href={listing.path} className="glass listing-card">
      <div className="listing-photo">
        {photo?.url
          ? <img className="listing-image" src={photo.url} alt={photo.alt_text || `${listing.title} — photo`} loading={priority ? "eager" : "lazy"} decoding="async" width={640} height={420} />
          : <div className="listing-image image-placeholder" aria-hidden="true"><HomeGlyph /><span>Photos coming soon</span></div>}
        {listing.media.length > 1 && <span className="photo-count">{listing.media.length} photos</span>}
      </div>
      <div className="listing-card-content">
        <div className="badge-row">
          <span className="status">Available</span>
          <VerificationBadge status={listing.property.verification_status} />
          {listing.property.landlord_verified && <span className="badge badge-landlord">ID-checked landlord</span>}
        </div>
        <p className="muted location">
          {listing.property.area}, {listing.property.city}
          {listing.distance_km != null && ` · ${listing.distance_km} km away`}
        </p>
        <h3>{listing.title}</h3>
        <strong className="price">{money(listing.monthly_rent)} <span>/ month</span></strong>
        <p className="listing-facts">{facts(listing).join(" · ")}</p>
      </div>
    </Link>
  );
}
