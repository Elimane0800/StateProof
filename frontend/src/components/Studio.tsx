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
      const firstViolation = payload.findings[0]?.node_id ?? null;
      setSelectedNodeId(firstViolation);
    });
    return () => {
      alive = false;
    };
  }, [auditId]);

  if (!audit) {
    return <div className="loading">Loading audit…</div>;
  }

  return (
    <div className="studio">
      <DriftScore score={audit.drift_score} prNumber={audit.pr_number} auditId={audit.audit_id} />
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
      {lastPatch && <div className="sr-only">Patch generated: {lastPatch.prompt}</div>}
    </div>
  );
}
