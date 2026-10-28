import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const site = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");
  return {
    rules: [{ userAgent: "*", allow: ["/", "/listings/", "/rentals/"],
              disallow: ["/tenant", "/landlord", "/admin", "/saved", "/profile", "/login", "/notifications", "/*?*cursor="] }],
    sitemap: `${site}/sitemap.xml`,
    host: site,
  };
}
