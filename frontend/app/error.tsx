"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <main className="shell state-page" role="alert">
      <div className="glass empty empty-state">
        <h1>Something went wrong</h1>
        <p>We could not load this page. Your information is safe. Please try again, or head back to the home page.</p>
        <div className="empty-actions"><button type="button" onClick={reset}>Try again</button><Link className="button button-secondary" href="/">Go to home</Link></div>
      </div>
    </main>
  );
}
