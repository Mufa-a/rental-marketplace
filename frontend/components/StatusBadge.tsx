import type { Tone } from "@/lib/status";

const ICON: Record<Tone, string> = { pending: "◔", approved: "✓", rejected: "✕", cancelled: "–", completed: "✓✓", neutral: "•" };

/** Colour is never the only signal: every status also has an icon and a text label. */
export default function StatusBadge({ label, tone }: { label: string; tone: Tone }) {
  return <span className={`status-badge tone-${tone}`}><span aria-hidden="true">{ICON[tone]}</span>{label}</span>;
}
