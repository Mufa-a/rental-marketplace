import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import SiteFooter from "@/components/SiteFooter";
import ThemeToggle from "@/components/ThemeToggle";
import "../styles/globals.css";
import "../styles/app.css";

// Variable fonts committed to the repo (SIL OFL 1.1, licences in app/fonts): builds never depend on
// Google Fonts being reachable, and visitors' browsers never contact Google.
const display = localFont({ src: "./fonts/fraunces-latin-variable.woff2", weight: "400 600", variable: "--font-display", display: "swap" });
const body = localFont({ src: "./fonts/manrope-latin-variable.woff2", weight: "400 800", variable: "--font-body", display: "swap" });

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

const themeScript = `try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"dark"}catch(e){document.documentElement.dataset.theme="dark"}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-KE" data-theme="dark" className={`${display.variable} ${body.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <div className="theme-toggle-fixed"><ThemeToggle /></div>
        <div id="main-content">{children}</div>
        <SiteFooter />
      </body>
    </html>
  );
}