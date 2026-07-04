import { useEffect, useState } from "react";
import { getReport } from "../api/client";
import type { AuditPayload, CursorPatch } from "../types/contract";
import { mockDetectComponents } from "../lib/detection";
import { DriftScore } from "./DriftScore";
import { GraphView } from "./GraphView";
import { ExplanationPanel } from "./ExplanationPanel";
import { type ReturnMedia } from "./ReturnMediaUpload";

interface Props {
  auditId: string;
}

export function Studio({ auditId }: Props) {
  const [audit, setAudit] = useState<AuditPayload | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [lastPatch, setLastPatch] = useState<CursorPatch | null>(null);
  const [returnMedia, setReturnMedia] = useState<ReturnMedia | null>(null);
  const [detectedComponentIds, setDetectedComponentIds] = useState<Set<string> | null>(null);

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

  useEffect(() => {
    return () => {
      if (returnMedia?.url.startsWith("blob:")) {
        URL.revokeObjectURL(returnMedia.url);
      }
    };
  }, [returnMedia]);

  const handleReturnUpload = (file: File, url: string) => {
    if (!audit) return;
    if (returnMedia?.url.startsWith("blob:")) {
      URL.revokeObjectURL(returnMedia.url);
    }
    setReturnMedia({
      url,
      type: file.type.startsWith("video/") ? "video" : "image",
      name: file.name,
    });
    setDetectedComponentIds(mockDetectComponents(audit));
  };

  const handleReturnClear = () => {
    if (returnMedia?.url.startsWith("blob:")) {
      URL.revokeObjectURL(returnMedia.url);
    }
    setReturnMedia(null);
    setDetectedComponentIds(null);
  };

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
          detectedComponentIds={detectedComponentIds}
        />
        <ExplanationPanel
          audit={audit}
          selectedNodeId={selectedNodeId}
          onGeneratedPatch={setLastPatch}
          returnMedia={returnMedia}
          onReturnUpload={handleReturnUpload}
          onReturnClear={handleReturnClear}
        />
      </main>
      {lastPatch && <div className="sr-only">Letter generated: {lastPatch.prompt}</div>}
    </div>
  );
}
