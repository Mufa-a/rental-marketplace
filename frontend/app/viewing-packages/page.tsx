import type { Metadata } from "next";
import LegalPage from "@/components/legal/LegalPage";
import { money, plural } from "@/lib/format";
import { LEGAL_DOCS } from "@/lib/legal";
import { serverGet } from "@/lib/server-api";
import type { Package } from "@/lib/types";

const doc = LEGAL_DOCS["viewing-packages"];

export const revalidate = 300;
export const metadata: Metadata = {
  title: doc.title,
  description: doc.description,
  alternates: { canonical: "/viewing-packages" },
};

type Prices = {
  viewing_packages: Package[];
  referral_fee_rules: { min_rent: number; max_rent: number | null; fee_type: string; amount: number; percent: string; currency: string }[];
  property_verification_fee: { amount: number; currency: string } | null;
};

export default async function Page() {
  const prices = await serverGet<Prices>("/payments/prices/", 300);
  return <LegalPage doc={doc}>
    {prices ? <div className="price-tables">
      <section className="glass price-card" aria-labelledby="tenant-prices"><h2 id="tenant-prices">Tenant viewing packages</h2>
        <table className="data-table"><thead><tr><th scope="col">Package</th><th scope="col">Price</th><th scope="col">Per viewing</th></tr></thead>
          <tbody>{prices.viewing_packages.map((p) => <tr key={p.id}><td>{plural(p.credits, "viewing")}</td><td>{money(p.price, p.currency)}</td><td>{money(p.price_per_viewing, p.currency)}</td></tr>)}</tbody></table></section>
      <section className="glass price-card" aria-labelledby="landlord-prices"><h2 id="landlord-prices">Landlord success fee</h2>
        <table className="data-table"><thead><tr><th scope="col">Agreed monthly rent</th><th scope="col">One-off fee</th></tr></thead>
          <tbody>{prices.referral_fee_rules.map((r, i) => <tr key={i}><td>{r.max_rent == null ? `${money(r.min_rent)} and above` : `${money(r.min_rent)} – ${money(r.max_rent)}`}</td><td>{r.fee_type === "percent" ? `${Number(r.percent)}% of one month's rent` : money(r.amount, r.currency)}</td></tr>)}</tbody></table>
        {prices.property_verification_fee && <p className="muted small">Optional property verification: {money(prices.property_verification_fee.amount, prices.property_verification_fee.currency)} (one-off).</p>}
      </section>
    </div> : <p className="notice notice-warning">Current prices could not be loaded. They are always shown before you pay.</p>}
  </LegalPage>;
}
