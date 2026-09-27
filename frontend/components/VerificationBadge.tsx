const COPY: Record<string, { label: string; className: string }> = {
  verified: { label: "Verified", className: "badge badge-verified" },
  pending: { label: "Verification pending", className: "badge badge-pending" },
  unverified: { label: "Unverified", className: "badge badge-unverified" },
  rejected: { label: "Verification rejected", className: "badge badge-unverified" },
};

export default function VerificationBadge({ status }: { status?: string | null }) {
  if (!status) return null;
  const copy = COPY[status] ?? COPY.unverified;
  return <span className={copy.className}>{copy.label}</span>;
}
