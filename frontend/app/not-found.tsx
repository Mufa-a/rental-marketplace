import Link from "next/link";
import SiteHeader from "@/components/SiteHeader";

export default function NotFound() {
  return (
    <main className="shell state-page">
      <SiteHeader right={<Link className="navlink" href="/">Browse homes</Link>} />
      <div className="glass empty empty-state">
        <h1>We could not find that page</h1>
        <p>The home may have been rented or removed, or the link may be out of date.</p>
        <div className="empty-actions"><Link className="button" href="/">Search available homes</Link></div>
      </div>
    </main>
  );
}
