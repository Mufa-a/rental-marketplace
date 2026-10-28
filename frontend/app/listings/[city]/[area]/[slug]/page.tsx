import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import ReportListingButton from "@/components/ReportListingButton";
import SafetyTips from "@/components/SafetyTips";
import SaveUnitButton from "@/components/SaveUnitButton";
import SiteHeader from "@/components/SiteHeader";
import VerificationBadge from "@/components/VerificationBadge";
import ViewBeacon from "@/components/ViewBeacon";
import ViewingRequestButton from "@/components/ViewingRequestButton";
import { bathroomsLabel, bedroomsLabel, date, FURNISHING, money, UNIT_TYPES } from "@/lib/format";
import { slug as toSlug } from "@/lib/search";
import { serverGet } from "@/lib/server-api";
import type { PublicListing } from "@/lib/types";

type PageProps = { params: Promise<{ city: string; area: string; slug: string }> };

// Short revalidation so a home that is let disappears quickly; the API itself never returns unavailable homes.
const getListing = (slug: string) => serverGet<PublicListing>(`/properties/listings/${encodeURIComponent(slug)}/`, 60);

const SCHEMA_TYPE: Record<string, string> = { apartment: "Apartment", studio: "Apartment", bedsitter: "Apartment", house: "SingleFamilyResidence", maisonette: "House", room: "Room" };

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const listing = await getListing((await params).slug);
  if (!listing) return { title: "Home not available", robots: { index: false } };
  const where = `${listing.property.area}, ${listing.property.city}`;
  const title = `${listing.title} — ${money(listing.monthly_rent)}/month in ${where}`;
  const description = `${bedroomsLabel(listing.bedrooms, listing.unit_type)} ${(UNIT_TYPES[listing.unit_type] ?? "home").toLowerCase()} to rent in ${where}, ${listing.property.county} for ${money(listing.monthly_rent)} per month. ${FURNISHING[listing.furnishing] ?? ""}. Request a viewing on Nyumbani.`;
  const image = listing.media[0]?.url;
  return {
    title, description, alternates: { canonical: listing.path },
    openGraph: { title, description, url: listing.path, type: "website", ...(image ? { images: [{ url: image }] } : {}) },
    twitter: { card: image ? "summary_large_image" : "summary", title, description },
  };
}

export default async function ListingPage({ params }: PageProps) {
  const { city, area, slug } = await params;
  const listing = await getListing(slug);
  if (!listing) notFound();
  if (`/listings/${city}/${area}/${slug}` !== listing.path) permanentRedirect(listing.path);

  const p = listing.property;
  const placePath = `/rentals/${toSlug(p.county)}/${toSlug(p.city)}/${toSlug(p.area)}`;
  // Only facts we actually have; no fabricated ratings, prices or availability.
  const schema = {
    "@context": "https://schema.org", "@type": SCHEMA_TYPE[listing.unit_type] ?? "Accommodation",
    name: listing.title, description: listing.description || undefined,
    numberOfBedrooms: listing.bedrooms, numberOfBathroomsTotal: Number(listing.bathrooms),
    ...(listing.floor_area_sqm ? { floorSize: { "@type": "QuantitativeValue", value: listing.floor_area_sqm, unitCode: "MTK" } } : {}),
    amenityFeature: listing.amenity_details.map((a) => ({ "@type": "LocationFeatureSpecification", name: a.name, value: true })),
    address: { "@type": "PostalAddress", addressLocality: p.area, addressRegion: p.county, addressCountry: p.country },
    ...(listing.media[0]?.url ? { image: listing.media.map((m) => m.url) } : {}),
  };
  const facts: [string, string][] = [
    ["Deposit", listing.security_deposit ? money(listing.security_deposit) : "Ask the landlord"],
    ["Bedrooms", bedroomsLabel(listing.bedrooms, listing.unit_type)],
    ["Bathrooms", bathroomsLabel(listing.bathrooms)],
    ["Type", UNIT_TYPES[listing.unit_type] ?? listing.unit_type],
    ["Furnishing", FURNISHING[listing.furnishing] ?? listing.furnishing],
    ...(listing.floor_area_sqm ? [["Size", `${listing.floor_area_sqm} m²`] as [string, string]] : []),
    ["Available", listing.available_from && new Date(listing.available_from) > new Date() ? `From ${date(listing.available_from)}` : "Now"],
  ];

  return <main className="shell">
    <SiteHeader />
    <ViewBeacon slug={listing.slug} />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} />
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <Link href="/">Home</Link><span aria-hidden="true">›</span>
      <Link href={placePath}>{p.area}, {p.city}</Link><span aria-hidden="true">›</span>
      <span aria-current="page">{listing.title}</span>
    </nav>
    <article className="listing-detail">
      <header className="detail-head">
        <div className="badge-row">
          <span className="status">Available to view</span>
          <VerificationBadge status={p.verification_status} showUnverified />
          {p.landlord_verified && <span className="badge badge-landlord" title="Our team checked this landlord's identity documents. Not a guarantee.">ID-checked landlord</span>}
        </div>
        <h1>{listing.title}</h1>
        <p className="muted">{p.area}, {p.city} · {p.county} County{listing.availability_confirmed_at ? ` · Availability confirmed ${date(listing.availability_confirmed_at)}` : ""}</p>
      </header>

      {listing.media.length > 0
        ? <div className={`detail-gallery count-${Math.min(listing.media.length, 5)}`}>{listing.media.map((image, index) => <img key={image.id ?? index} src={image.url} alt={image.alt_text || `${listing.title} — photo ${index + 1}`} loading={index < 2 ? "eager" : "lazy"} decoding="async" />)}</div>
        : <div className="detail-no-image glass">The landlord has not added photos yet. Ask to see the home before deciding.</div>}

      <div className="detail-content">
        <div className="detail-main">
          <p className="detail-price">{money(listing.monthly_rent)} <span>/ month</span></p>
          <dl className="fact-grid">{facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          <SaveUnitButton unitId={listing.id} />
          <h2>About this home</h2>
          <p className="detail-description">{listing.description || "The landlord has not added a description yet."}</p>
          {listing.amenity_details.length > 0 && <><h2>What it offers</h2><ul className="amenities">{listing.amenity_details.map((a) => <li key={a.slug}>{a.name}</li>)}</ul></>}
          <h2>Location</h2>
          <p className="muted">In {p.area}, {p.city}. The exact address and the landlord&apos;s phone number are shared with you as soon as the landlord approves your viewing — this keeps both sides safe and every viewing on record.</p>
          <section className="listing-safety" aria-label="Safety">
            <h2>Before you commit</h2>
            <p className="muted small">Verification badges mean our team checked documents. They are not a guarantee that a landlord or home is legitimate.</p>
            <SafetyTips compact />
            <ReportListingButton unitId={listing.id} />
          </section>
        </div>
        <aside className="viewing-panel glass" aria-labelledby="view-title">
          <p className="eyebrow">See it in person</p>
          <h2 id="view-title">Arrange a viewing</h2>
          <ViewingRequestButton unitId={listing.id} />
        </aside>
      </div>
    </article>
  </main>;
}
