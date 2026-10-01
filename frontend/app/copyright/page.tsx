import type { Metadata } from "next";
import LegalPage from "@/components/legal/LegalPage";
import { LEGAL_DOCS } from "@/lib/legal";

const doc = LEGAL_DOCS["copyright"];

export const revalidate = 86400;
export const metadata: Metadata = {
  title: doc.title,
  description: doc.description,
  alternates: { canonical: "/copyright" },
  openGraph: { title: doc.title, description: doc.description, url: "/copyright", type: "article" },
};

export default function Page() {
  return <LegalPage doc={doc} />;
}
