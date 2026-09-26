import type { MetadataRoute } from "next";

type Listing = { slug?: string; property?: { city?: string; area?: string } };
type SearchPage = { next?: string | null; results?: Listing[] };

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const site = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const entries: MetadataRoute.Sitemap = [{ url: site, changeFrequency: "daily", priority: 1 }];
  let next: string | null = `${api}/properties/search/`;
  let pages = 0;
  while (next && pages < 20) {
    try {
      const response = await fetch(next, { next: { revalidate: 3600 } });
      if (!response.ok) break;
      const body = (await response.json()) as SearchPage;
      for (const listing of body.results ?? []) {
        if (!listing.slug || !listing.property?.city || !listing.property?.area) continue;
        const path = ["listings", listing.property.city, listing.property.area, listing.slug]
          .map((part) => encodeURIComponent(part.toLowerCase().replaceAll(" ", "-"))).join("/");
        entries.push({ url: `${site}/${path}`, changeFrequency: "weekly", priority: 0.7 });
      }
      next = body.next ?? null;
      pages += 1;
    } catch {
      break;
    }
  }
  return entries;
}
