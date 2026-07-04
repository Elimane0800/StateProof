import { useEffect, useState } from "react";
import type { Classification } from "../types/contract";

interface Props {
  score: number;
  auditId: string;
  assetId?: string;
  selectedClassification?: Classification | null;
}

const STEPS = ["Return", "Compare", "Resolve"] as const;
const CURRENT_STEP = 1;

function splitPlate(plate: string): { country: string; number: string } {
  const parts = plate.split("-");
  if (parts.length >= 3) {
    return { country: parts[0], number: parts.slice(1).join("-") };
  }
  return { country: "EU", number: plate };
}

export function DriftScore({ score, auditId, assetId, selectedClassification }: Props) {
  const [displayScore, setDisplayScore] = useState(0);
  const resolved = score === 0;
  const color = resolved ? "#22c55e" : score < 40 ? "#f59e0b" : "#ef4444";
  const plate = assetId ?? "AB-123-CD";
  const { country, number } = splitPlate(plate);
  const showReducedHint =
    selectedClassification === "technical_noise" ||
    selectedClassification === "intentional_evolution";

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

      <div className="journey">
        <nav className="journey__steps" aria-label="Inspection journey">
          {STEPS.map((step, i) => (
            <span
              key={step}
              className={`journey__step${i === CURRENT_STEP ? " journey__step--active" : ""}${i < CURRENT_STEP ? " journey__step--done" : ""}`}
            >
              {i > 0 && <span className="journey__arrow">→</span>}
              {step}
            </span>
          ))}
        </nav>
        <span className="journey__subtitle">Returning vehicle {plate}</span>
      </div>

      <div className="topbar__meta">
        <span className="topbar__plate" title="This car's ledger">
          <span className="topbar__plate-eu">
            <span className="topbar__plate-stars">★</span>
            <span className="topbar__plate-country">{country}</span>
          </span>
          <span className="topbar__plate-number">{number}</span>
        </span>
        <span className="topbar__audit">{auditId}</span>
        <div className="drift" style={{ borderColor: color }}>
          <span className="drift__label">
            {resolved ? "No liability" : "Damage Charge Score"}
          </span>
          <span className="drift__value" style={{ color }}>
            €{displayScore}
          </span>
          {showReducedHint && (
            <span className="drift__hint">
              {selectedClassification === "technical_noise"
                ? "This part: €0 — registered wear"
                : "This part: €0 — agreed at pickup"}
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
