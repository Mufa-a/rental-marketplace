import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import SearchExperience from "@/components/SearchExperience";
import SiteHeader from "@/components/SiteHeader";
import { EMPTY_FILTERS, filtersFrom, queryString, unslug } from "@/lib/search";
import { serverGet } from "@/lib/server-api";
import type { Amenity, SearchPage } from "@/lib/types";

type PageProps = { params: Promise<{ location: string[] }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

const title = (value: string) => value.replace(/\b\w/g, (c) => c.toUpperCase());

/** /rentals/<county>[/<town>[/<estate>]] — crawlable landing pages for each place with listings. */
function placeFilters(segments: string[]) {
  if (segments.length < 1 || segments.length > 3) return null;
  const [county, town, estate] = segments.map(unslug);
  return { county, town: town ?? "", estate: estate ?? "" };
}

function placeName(place: { county: string; town: string; estate: string }) {
  const parts = Array.from(new Set([place.estate, place.town].filter(Boolean).map(title)));
  return parts.length ? parts.join(", ") : `${title(place.county)} County`;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { location } = await params;
  const place = placeFilters(location);
  if (!place) return {};
  const name = placeName(place);
  const data = await serverGet<SearchPage>(`/properties/search/?${queryString({ ...EMPTY_FILTERS, ...place })}`, 300);
  const path = `/rentals/${location.map(encodeURIComponent).join("/")}`;
  return {
    title: `Houses and apartments for rent in ${name}`,
    description: `${data?.count ?? 0} rental home${data?.count === 1 ? "" : "s"} available in ${name}, with monthly rent shown up front and viewings arranged with the landlord.`,
    alternates: { canonical: path },
    // Thin pages (no listings) are not worth indexing.
    robots: data && data.count > 0 ? undefined : { index: false, follow: true },
  };
}

export default async function PlacePage({ params, searchParams }: PageProps) {
  const { location } = await params;
  const place = placeFilters(location);
  if (!place) notFound();
  const filters = { ...filtersFrom(await searchParams), ...place };
  const [initial, amenities] = await Promise.all([
    serverGet<SearchPage>(`/properties/search/?${queryString(filters)}`, 60),
    serverGet<Amenity[]>("/properties/amenities/", 3600),
  ]);
  const name = placeName(place);
  return <main className="shell">
    <SiteHeader />
    <nav className="breadcrumbs" aria-label="Breadcrumb"><Link href="/">Home</Link><span aria-hidden="true">›</span><span aria-current="page">{name}</span></nav>
    <SearchExperience initial={initial} initialFilters={filters} amenities={amenities ?? []} heading={`Available in ${name}`} heroClassName="place-hero"
      intro={<><p className="eyebrow">Rentals in {title(place.county)}</p><h1>Homes for rent in {name}</h1></>} />
  </main>;
}
