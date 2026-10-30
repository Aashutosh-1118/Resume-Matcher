// Small shared building blocks used across pages.

export function scoreTone(score) {
  if (score >= 70) return "good";
  if (score >= 40) return "mid";
  return "low";
}

export function ScoreRing({ score, size = 120 }) {
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const value = Math.max(0, Math.min(100, score ?? 0));
  const dash = (value / 100) * circumference;
  return (
    <div className={`score-ring tone-${scoreTone(value)}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label={`Match score ${value} percent`}>
        <circle cx="50" cy="50" r={radius} className="ring-bg" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          className="ring-fg"
          strokeDasharray={`${dash} ${circumference - dash}`}
          transform="rotate(-90 50 50)"
        />
      </svg>
      <div className="ring-label">
        <strong>{Number.isInteger(value) ? value : value.toFixed(1)}</strong>
        <span>%</span>
      </div>
    </div>
  );
}

export function ScoreBar({ score }) {
  const value = Math.max(0, Math.min(100, score ?? 0));
  return (
    <div className="score-bar" title={`${value}%`}>
      <div className={`score-bar-fill tone-${scoreTone(value)}`} style={{ width: `${value}%` }} />
      <span>{value}</span>
    </div>
  );
}

export function Chips({ items, tone, empty = "None" }) {
  if (!items || items.length === 0) return <span className="muted">{empty}</span>;
  return (
    <div className="chips">
      {items.map((s) => (
        <span key={s} className={`chip chip-${tone}`}>
          {s}
        </span>
      ))}
    </div>
  );
}

export function Alert({ kind = "error", children }) {
  if (!children) return null;
  return <div className={`alert alert-${kind}`} role={kind === "error" ? "alert" : "status"}>{children}</div>;
}

export function Spinner({ label }) {
  return (
    <div className="loading-row">
      <div className="spinner" />
      {label && <span>{label}</span>}
    </div>
  );
}

export function formatDate(iso) {
  if (!iso) return "";
  // The server sends UTC without a zone marker for some databases, so add one if missing.
  const value = /[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
