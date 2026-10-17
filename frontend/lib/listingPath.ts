/**
 * The one place that decides what a listing's public URL looks like.
 *
 * Links, map popups, the canonical URL and the sitemap must all agree, otherwise search engines
 * see several URLs for the same page. The route itself only uses the slug; city and area are
 * there for readability, so older links with a different spelling keep working.
 */
const segment = (value: string) => encodeURIComponent(value.trim().toLowerCase().replace(/\s+/g, "-"));

export function listingPath(city: string, area: string, slug: string): string {
  return `/listings/${segment(city)}/${segment(area)}/${encodeURIComponent(slug)}`;
}
