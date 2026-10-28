import type { MetadataRoute } from "next";
import { slug } from "@/lib/search";
import { SERVER_API } from "@/lib/server-api";
import type { SearchPage } from "@/lib/types";

export const revalidate = 3600;

/** Public pages only. Dashboards, accounts and anything about tenants or bookings are never listed. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const site = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");
  const entries: MetadataRoute.Sitemap = [
    { url: site, changeFrequency: "daily", priority: 1 },
    ...["viewing-packages", "listing-rules", "terms", "privacy", "cookies", "data-protection", "copyright", "contact"]
      .map((page) => ({ url: `${site}/${page}`, changeFrequency: "monthly" as const, priority: 0.3 })),
  ];
  const places = new Set<string>();
  let cursor: string | null = "";
  for (let pages = 0; cursor !== null && pages < 50; pages += 1) {
    try {
      const response = await fetch(`${SERVER_API}/properties/search/?ordering=-created_at${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, { next: { revalidate: 3600 } });
      if (!response.ok) break;
      const body = (await response.json()) as SearchPage;
      for (const listing of body.results) {
        entries.push({ url: `${site}${listing.path}`, lastModified: listing.updated_at, changeFrequency: "weekly", priority: 0.7 });
        const p = listing.property;
        places.add(`/rentals/${slug(p.county)}`);
        places.add(`/rentals/${slug(p.county)}/${slug(p.city)}`);
        places.add(`/rentals/${slug(p.county)}/${slug(p.city)}/${slug(p.area)}`);
      }
      cursor = body.next ? new URL(body.next).searchParams.get("cursor") : null;
    } catch { break; }
  }
  for (const place of places) entries.push({ url: `${site}${place}`, changeFrequency: "daily", priority: 0.6 });
  return entries;
}
