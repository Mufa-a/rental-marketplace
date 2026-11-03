const COPY: Record<string, { label: string; className: string; title: string } | null> = {
  verified: { label: "Verified property", className: "badge badge-verified", title: "Our team checked this property. This is not a guarantee — always view before you pay." },
  pending: null,
  needs_review: null,
  unverified: null,
  rejected: null,
};

/** Only a positive, checked status is shown publicly; nothing else is ever presented as verified. */
export default function VerificationBadge({ status, showUnverified = false }: { status?: string | null; showUnverified?: boolean }) {
  const copy = status ? COPY[status] : null;
  if (copy) return <span className={copy.className} title={copy.title}>{copy.label}</span>;
  return showUnverified ? <span className="badge badge-unverified" title="This property has not been checked by our team.">Not yet verified</span> : null;
}
