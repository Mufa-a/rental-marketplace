import type { Metadata } from "next";
import Link from "next/link";
import HeroArt from "@/components/HeroArt";
import SafetyTips from "@/components/SafetyTips";
import SearchExperience from "@/components/SearchExperience";
import SiteHeader from "@/components/SiteHeader";
import { filtersFrom, queryString } from "@/lib/search";
import { serverGet } from "@/lib/server-api";
import type { Amenity, SearchPage } from "@/lib/types";

export const metadata: Metadata = {
  title: { absolute: "Nyumbani — houses and apartments for rent in Kenya" },
  description: "Search rentals across Kenya by estate, town or county. Clear monthly rent, recently confirmed availability, and viewings arranged with the landlord.",
  alternates: { canonical: "/" },
};

const STEPS = [
  { title: "Search for free", body: "Filter by estate, rent, bedrooms and must-haves. Every home shows its monthly rent up front." },
  { title: "Request a viewing", body: "Use a viewing credit to ask the landlord for a time. If they decline or don't reply, the credit comes back." },
  { title: "View, then decide", body: "Once approved you get the address and the landlord's contact. Rent and deposit are agreed directly with the landlord." },
];

type PageProps = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function Home({ searchParams }: PageProps) {
  const filters = filtersFrom(await searchParams);
  const query = queryString(filters);
  const [initial, amenities] = await Promise.all([
    serverGet<SearchPage>(`/properties/search/${query ? `?${query}` : ""}`, 60),
    serverGet<Amenity[]>("/properties/amenities/", 3600),
  ]);

  return <main className="shell">
    <SiteHeader />
    <SearchExperience initial={initial} initialFilters={filters} amenities={amenities ?? []} intro={
      <div className="hero-v2-top">
        <div className="hero-v2-copy">
          <span className="hero-pill"><i />Rentals across Kenya</span>
          <h1>Find a place that feels like <em>home.</em></h1>
          <p className="muted">Real listings with clear monthly rent. Browse for free, request a viewing when you are ready, and agree terms directly with the landlord.</p>
        </div>
        <HeroArt />
      </div>} />

    <section className="how" aria-labelledby="how-title">
      <div className="how-head"><p className="eyebrow">How it works</p><h2 id="how-title">From search to keys, in three clear steps.</h2></div>
      <div className="steps">{STEPS.map((step, index) => <article className="glass step" key={step.title}><span className="step-num" aria-hidden="true">{index + 1}</span><h3>{step.title}</h3><p>{step.body}</p></article>)}</div>
      <p className="muted how-foot">Viewing packages start from the price shown on <Link href="/viewing-packages">viewing packages</Link>. We never collect rent or deposits.</p>
    </section>

    <section className="audience" aria-label="For tenants and landlords">
      <article className="glass audience-card"><p className="eyebrow">For tenants</p><h2>Look freely, ask when you are ready</h2><ul><li>Browsing and saving homes is always free.</li><li>Credits are only used when a landlord approves your viewing.</li><li>Report anything suspicious in one tap.</li></ul><Link className="button button-small" href="/login?mode=signup">Create a tenant account</Link></article>
      <article className="glass audience-card"><p className="eyebrow">For landlords</p><h2>Reach tenants who want to view</h2><ul><li>Listing is free. A success fee applies only when a platform viewing becomes a tenancy.</li><li>Approve viewings, share the address only with approved tenants.</li><li>See views, requests and rentals for every unit.</li></ul><Link className="button button-small" href="/login?mode=signup&role=landlord">List a home</Link></article>
    </section>

    <section className="glass trust-section" aria-labelledby="trust-title">
      <div className="how-head"><p className="eyebrow">Trust &amp; safety</p><h2 id="trust-title">Rent with your eyes open.</h2><p className="muted">Nyumbani connects tenants and landlords. Verification badges mean our team checked documents — they are not a guarantee. Always view before you pay anything.</p></div>
      <SafetyTips compact />
    </section>
  </main>;
}
