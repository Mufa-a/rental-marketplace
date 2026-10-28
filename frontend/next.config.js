/** @type {import('next').NextConfig} */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Geolocation is only ever used by the opt-in "Homes near me" search on this site.
  { key: "Permissions-Policy", value: "geolocation=(self), camera=(), microphone=(), payment=()" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
];

const nextConfig = {
  poweredByHeader: false,
  // Smaller production image: `next build` emits a self-contained server in .next/standalone.
  output: "standalone",
  // Listing photos are rendered with plain <img> tags straight from R2. Keeping the
  // built-in optimizer off removes the /_next/image endpoint, which has had several
  // unauthenticated DoS/RCE advisories, from the attack surface entirely.
  images: { unoptimized: true },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

module.exports = nextConfig;
