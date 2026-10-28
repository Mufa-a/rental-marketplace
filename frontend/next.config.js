/** @type {import('next').NextConfig} */
const api = new URL(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1");
const isDev = process.env.NODE_ENV !== "production";

// Next.js inlines small bootstrap scripts, so script-src needs 'unsafe-inline' unless nonces are
// introduced via middleware (which would make every page dynamic). The policy still blocks third-party
// scripts (except the pinned, SRI-checked Leaflet build), plugins, framing and form posts elsewhere.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' https://unpkg.com${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline' https://unpkg.com",
  "img-src 'self' data: blob: https:",
  "font-src 'self'",
  `connect-src 'self' ${api.origin} https://*.r2.cloudflarestorage.com${isDev ? " ws:" : ""}`,
  "frame-src 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  // Only when the API is HTTPS too; otherwise a local production build could not reach an http API.
  ...(!isDev && api.protocol === "https:" ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Geolocation is only ever used by the opt-in "Homes near me" search and the landlord map pin.
  { key: "Permissions-Policy", value: "geolocation=(self), camera=(), microphone=(), payment=()" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
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
    return [
      { source: "/:path*", headers: securityHeaders },
      // Private pages must never be cached by shared caches or indexed.
      ...["/tenant", "/landlord", "/admin", "/saved", "/profile", "/notifications", "/login"].map((source) => ({
        source, headers: [{ key: "Cache-Control", value: "private, no-store" }, { key: "X-Robots-Tag", value: "noindex, nofollow" }],
      })),
    ];
  },
};

module.exports = nextConfig;
