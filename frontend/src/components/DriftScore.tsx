import { useEffect, useState } from "react";

interface Props {
  score: number;
  auditId: string;
  assetId?: string;
}

export function DriftScore({ score, auditId, assetId }: Props) {
  const [displayScore, setDisplayScore] = useState(0);
  const resolved = score === 0;
  const color = resolved ? "#22c55e" : score < 40 ? "#f59e0b" : "#ef4444";
  const plate = assetId ?? "AB-123-CD";

  useEffect(() => {
    if (resolved) {
      setDisplayScore(0);
      return;
    }
    const duration = 700;
    const start = performance.now();
    let frame: number;
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - (1 - t) ** 3;
      setDisplayScore(Math.round(eased * score));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [score, resolved]);

  return (
    <header className="topbar">
      <div className="topbar__brand">
        <span className="topbar__logo">◈</span>
        <div>
          <strong>StateProof</strong>
          <span className="topbar__sub">Proof of how it was.</span>
        </div>
      </div>
      <div className="topbar__meta">
        <span className="topbar__plate" title="This car's ledger">
          {plate}
        </span>
        <span className="topbar__audit">{auditId}</span>
        <div className="drift" style={{ borderColor: color }}>
          <span className="drift__label">
            {resolved ? "No liability" : "Damage Charge Score"}
          </span>
          <span className="drift__value" style={{ color }}>
            €{displayScore}
          </span>
        </div>
      </div>
    </header>
  );
}
