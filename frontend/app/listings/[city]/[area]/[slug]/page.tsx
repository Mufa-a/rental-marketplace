import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ViewingRequestButton from "@/components/ViewingRequestButton";
import SaveUnitButton from "@/components/SaveUnitButton";

type Listing = { id: number; title: string; monthly_rent: number; bedrooms: number; bathrooms: string; description: string; available: boolean; property: { name: string; area: string; city: string; county: string; country: string }; media: { url: string; alt_text: string }[]; amenity_details: { name: string }[] };
const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function getListing(slug: string): Promise<Listing | null> {
  const response = await fetch(`${baseUrl}/properties/listings/${slug}/`, { next: { revalidate: 300 } });
  return response.ok ? response.json() : null;
}

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const listing = await getListing(params.slug);
  if (!listing) return {};
  return { title: `${listing.title} in ${listing.property.area}, ${listing.property.city} | Rental Marketplace`, description: `${listing.bedrooms} bedroom rental for KSh ${listing.monthly_rent.toLocaleString()} per month.` };
}

export default async function ListingPage({ params }: { params: { slug: string } }) {
  const listing = await getListing(params.slug);
  if (!listing) notFound();
  const schema = { "@context": "https://schema.org", "@type": "Apartment", name: `${listing.property.name} - ${listing.title}`, numberOfRooms: listing.bedrooms, address: { "@type": "PostalAddress", addressLocality: listing.property.area, addressRegion: listing.property.county, addressCountry: "KE" }, offers: { "@type": "Offer", price: String(listing.monthly_rent), priceCurrency: "KES", availability: "https://schema.org/InStock" } };
  const schemaJson = JSON.stringify(schema).replace(/</g, "\\u003c");
  return <main className="shell"><header className="topnav"><Link className="brand" href="/">Nyumbani</Link><Link className="navlink" href="/">Browse homes</Link></header><script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schemaJson }} /><article className="glass listing-detail">
    <p className="eyebrow">{listing.property.area}, {listing.property.city}</p><span className="status">Available to view</span><h1 style={{ fontSize: "clamp(34px,5vw,52px)", margin: "14px 0 10px" }}>{listing.title}</h1><p className="muted">{listing.property.name} · {listing.property.area}, {listing.property.city}</p>
    {listing.media.length > 0 ? <div className="detail-gallery">{listing.media.map((image, index) => <img key={`${image.url}-${index}`} src={image.url} alt={image.alt_text || `${listing.title} rental photo ${index + 1}`} />)}</div> : <div className="detail-no-image">Photos will be added by the landlord.</div>}
    <div className="detail-content"><div><h2 className="detail-price">KSh {listing.monthly_rent.toLocaleString()} <span>/ month</span></h2><p className="muted">{listing.bedrooms === 0 ? "Bedsitter / studio" : `${listing.bedrooms} bedroom${listing.bedrooms === 1 ? "" : "s"}`} · {listing.bathrooms} bathroom</p><SaveUnitButton unitId={listing.id} /><h2>About this home</h2><p className="detail-description">{listing.description || "Contact the landlord to learn more about this home."}</p>{listing.amenity_details.length > 0 && <><h2>What it offers</h2><div className="amenities">{listing.amenity_details.map((a) => <span key={a.name}>{a.name}</span>)}</div></>}</div><aside className="viewing-panel glass"><p className="eyebrow">See it in person</p><h2>Arrange a viewing</h2><p className="muted">Send a request to the landlord and manage the response in your dashboard.</p><ViewingRequestButton unitId={listing.id} /></aside></div>
  </article></main>;
}
