import type { Metadata, Viewport } from "next";
import SiteFooter from "@/components/SiteFooter";
import "../styles/globals.css";

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");
const description = "Search rentals in Kenya with clear monthly prices and confirmed availability, then arrange viewings with landlords.";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: { default: "Nyumbani — find a rental home in Kenya", template: "%s | Nyumbani" },
  description,
  alternates: { canonical: "/" },
  openGraph: { type: "website", siteName: "Nyumbani", title: "Nyumbani — find a rental home in Kenya", description, url: "/", locale: "en_KE" },
  twitter: { card: "summary", title: "Nyumbani — find a rental home in Kenya", description },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0b1821" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Manrope:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <div id="main-content">{children}</div>
        <SiteFooter />
      </body>
    </html>
  );
}
