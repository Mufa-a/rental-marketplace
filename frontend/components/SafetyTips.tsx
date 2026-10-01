/**
 * Safety guidance. Deliberately makes no claim that listings are verified — verification
 * labels appear per property only when the platform has actually recorded them.
 */
export default function SafetyTips({ compact = false }: { compact?: boolean }) {
  const tips = [
    ["Check the details yourself", "Visit the home and confirm it matches the listing before you commit to anything."],
    ["Attend real viewings", "Arrange viewings through Nyumbani so both sides have a record of the request, time and outcome."],
    ["Be careful with payments", "Be wary of anyone who asks for money before you have seen the home, or asks you to pay outside the platform to “reserve” it."],
    ["Report what looks wrong", "Use “Report this listing” on any listing that seems fake, misleading or abusive."],
    ["Share only what is needed", "Never share your one-time code, and avoid giving more personal information than you have to."],
  ];
  return (
    <div className={`safety-tips${compact ? " safety-compact" : ""}`}>
      {tips.map(([title, body]) => (
        <div key={title}><strong>{title}</strong><p>{body}</p></div>
      ))}
    </div>
  );
}
