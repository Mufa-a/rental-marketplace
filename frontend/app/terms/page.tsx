import type { Metadata } from "next";
import LegalPage from "@/components/legal/LegalPage";
import { LEGAL_DOCS } from "@/lib/legal";

const doc = LEGAL_DOCS["terms"];

export const revalidate = 86400;
export const metadata: Metadata = {
  title: doc.title,
  description: doc.description,
  alternates: { canonical: "/terms" },
  openGraph: { title: doc.title, description: doc.description, url: "/terms", type: "article" },
};

export default function Page() {
  return <LegalPage doc={doc} />;
}
