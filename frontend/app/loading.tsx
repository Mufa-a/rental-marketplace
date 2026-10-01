export default function Loading() {
  return (
    <main className="shell state-page" aria-busy="true" aria-live="polite">
      <div className="glass skeleton-card" role="status" aria-label="Loading" />
    </main>
  );
}
