import { useEffect, useState } from "react";
import { getReport } from "../api/client";
import type { AuditPayload, CursorPatch } from "../types/contract";
import { DriftScore } from "./DriftScore";
import { GraphView } from "./GraphView";
import { ExplanationPanel } from "./ExplanationPanel";

interface Props {
  auditId: string;
}

export function Studio({ auditId }: Props) {
  const [audit, setAudit] = useState<AuditPayload | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [lastPatch, setLastPatch] = useState<CursorPatch | null>(null);

  useEffect(() => {
    let alive = true;
    getReport(auditId).then((payload) => {
      if (!alive) return;
      setAudit(payload);
      const registryHero =
        payload.ignored_as_noise.find((n) => n.node_id === "door_fl")?.node_id ??
        payload.ignored_as_noise.find((n) =>
          n.reasoning.toLowerCase().includes("registry")
        )?.node_id ??
        null;
      setSelectedNodeId(registryHero ?? payload.findings[0]?.node_id ?? null);
    });
    return () => {
      alive = false;
    };
  }, [auditId]);

  if (!audit) {
    return <div className="loading">Loading audit…</div>;
  }

  const selectedClassification =
    audit.findings.find((f) => f.node_id === selectedNodeId)?.classification ??
    (audit.ignored_as_noise.some((n) => n.node_id === selectedNodeId)
      ? ("technical_noise" as const)
      : audit.evolution_proposals.some((e) => e.node_id === selectedNodeId)
        ? ("intentional_evolution" as const)
        : null);

  return (
    <div className="studio">
      <DriftScore
        score={audit.drift_score}
        auditId={audit.audit_id}
        assetId={audit.asset_id}
        selectedClassification={selectedClassification}
      />
      <main className="studio__body">
        <GraphView
          audit={audit}
          selectedNodeId={selectedNodeId}
          onSelectNode={setSelectedNodeId}
        />
        <ExplanationPanel
          audit={audit}
          selectedNodeId={selectedNodeId}
          onGeneratedPatch={setLastPatch}
        />
      </main>
      {lastPatch && <div className="sr-only">Letter generated: {lastPatch.prompt}</div>}
    </div>
  );
}
