// Decorative hero illustration: an evening apartment skyline drawn in SVG so
// the homepage has a real visual identity without depending on photo assets.
// Window lighting is computed from indices (no randomness) so server and
// client renders always match.
const GROUND = 320;
const BUILDINGS = [
  { x: 18, w: 86, h: 132 },
  { x: 112, w: 72, h: 196 },
  { x: 192, w: 104, h: 112 },
  { x: 304, w: 78, h: 168 },
  { x: 390, w: 72, h: 124 },
];
const STARS = [[46, 40], [92, 66], [150, 28], [214, 58], [262, 36], [318, 70], [60, 100]];

export default function HeroArt() {
  return (
    <div className="hero-art" aria-hidden="true">
      <svg viewBox="0 0 480 396" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="hero-sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#1b4a48" />
            <stop offset="0.65" stopColor="#0f2b31" />
            <stop offset="1" stopColor="#0b1821" />
          </linearGradient>
          <linearGradient id="hero-building" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#2a5147" />
            <stop offset="1" stopColor="#15302f" />
          </linearGradient>
          <radialGradient id="hero-sun" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#ffd28b" stopOpacity="0.95" />
            <stop offset="0.45" stopColor="#f5bd68" stopOpacity="0.35" />
            <stop offset="1" stopColor="#f5bd68" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="480" height="396" fill="url(#hero-sky)" />
        <circle cx="384" cy="86" r="86" fill="url(#hero-sun)" />
        <circle cx="384" cy="86" r="26" fill="#f5bd68" />
        {STARS.map(([x, y]) => <circle key={`s-${x}-${y}`} cx={x} cy={y} r="1.6" fill="#f9f7f2" opacity="0.55" />)}
        {BUILDINGS.map((b, bi) => {
          const cols = Math.floor((b.w - 16) / 22);
          const rows = Math.floor((b.h - 30) / 26);
          const top = GROUND - b.h;
          return (
            <g key={`b-${b.x}`}>
              <rect x={b.x} y={top} width={b.w} height={b.h} rx="4" fill="url(#hero-building)" stroke="rgba(255,255,255,0.08)" />
              {Array.from({ length: rows }).flatMap((_, r) =>
                Array.from({ length: cols }).map((__, c) => {
                  const lit = (c * 5 + r * 3 + bi * 2) % 7 < 3;
                  return (
                    <rect
                      key={`w-${b.x}-${r}-${c}`}
                      x={b.x + 12 + c * 22}
                      y={top + 14 + r * 26}
                      width="12"
                      height="15"
                      rx="2"
                      fill={lit ? "#f5bd68" : "rgba(255,255,255,0.07)"}
                      opacity={lit ? 0.92 : 1}
                    />
                  );
                }),
              )}
              <rect x={b.x + b.w / 2 - 7} y={GROUND - 22} width="14" height="22" rx="2" fill="#f5bd68" opacity="0.85" />
            </g>
          );
        })}
        <rect x="0" y={GROUND} width="480" height={396 - GROUND} fill="#0a151c" />
        <rect x="0" y={GROUND} width="480" height="2" fill="rgba(156,221,189,0.25)" />
        {[[106, 0], [188, 1], [298, 2], [386, 3]].map(([x, i]) => (
          <g key={`t-${i}`}>
            <rect x={x - 2} y={GROUND - 22} width="4" height="22" fill="#1b3a30" />
            <circle cx={x} cy={GROUND - 30} r="13" fill="#1f5240" />
          </g>
        ))}
      </svg>
      <span className="art-chip a">Direct with landlords</span>
      <span className="art-chip b">Verification badges</span>
      <span className="art-chip c">Track every viewing</span>
    </div>
  );
}
