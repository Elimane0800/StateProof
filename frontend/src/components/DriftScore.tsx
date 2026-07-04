interface Props {
  score: number;
  prNumber: number;
  auditId: string;
}

export function DriftScore({ score, prNumber, auditId }: Props) {
  const resolved = score === 0;
  const color = resolved ? "#22c55e" : score < 40 ? "#f59e0b" : "#ef4444";
  return (
    <header className="topbar">
      <div className="topbar__brand">
        <span className="topbar__logo">◈</span>
        <div>
          <strong>SynchronAIse</strong>
          <span className="topbar__sub">Graph Reconciliation Studio</span>
        </div>
      </div>
      <div className="topbar__meta">
        <span className="topbar__pr">PR #{prNumber}</span>
        <span className="topbar__audit">{auditId}</span>
        <div className="drift" style={{ borderColor: color }}>
          <span className="drift__label">{resolved ? "Resolved" : "Drift score"}</span>
          <span className="drift__value" style={{ color }}>
            {score}
          </span>
        </div>
      </div>
    </header>
  );
}
