import { useEffect, useState } from "react";
import { getReport, runReturnInspection, startInspection } from "../api/client";
import type { AuditPayload, CursorPatch } from "../types/contract";
import { DriftScore } from "./DriftScore";
import { GraphView } from "./GraphView";
import { ExplanationPanel } from "./ExplanationPanel";
import { type ReturnMedia } from "./ExplanationPanel";
import { IntakePanel, type IntakeResult } from "./IntakePanel";

interface Props {
  /** Deep-linked report id (#/report/:id), or null to start on the intake screen. */
  auditId: string | null;
}

export function Studio({ auditId }: Props) {
  const [audit, setAudit] = useState<AuditPayload | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [lastPatch, setLastPatch] = useState<CursorPatch | null>(null);
  const [pickupMedia, setPickupMedia] = useState<ReturnMedia | null>(null);
  const [returnMedia, setReturnMedia] = useState<ReturnMedia | null>(null);
  const [detectedComponentIds, setDetectedComponentIds] = useState<Set<string> | null>(null);

  const selectRegistryHero = (payload: AuditPayload) =>
    payload.ignored_as_noise.find((n) => n.node_id === "door_fl")?.node_id ??
    payload.ignored_as_noise.find((n) => n.reasoning.toLowerCase().includes("registry"))?.node_id ??
    payload.findings[0]?.node_id ??
    null;

  useEffect(() => {
    if (!auditId) return;
    let alive = true;
    getReport(auditId).then((payload) => {
      if (!alive) return;
      setAudit(payload);
      setSelectedNodeId(selectRegistryHero(payload));
    });
    return () => {
      alive = false;
    };
  }, [auditId]);

  const handleIntakeRun = async (intake: IntakeResult) => {
    setPickupMedia({
      url: intake.pickupUrl,
      type: intake.pickupFile.type.startsWith("video/") ? "video" : "image",
      name: intake.pickupFile.name,
    });
    setReturnMedia({
      url: intake.returnUrl,
      type: intake.returnFile.type.startsWith("video/") ? "video" : "image",
      name: intake.returnFile.name,
    });
    const { audit: nextAudit, detected } = await startInspection(
      intake.plate,
      intake.pickupFile,
      intake.returnFile
    );
    setAudit(nextAudit);
    setDetectedComponentIds(detected);
    setSelectedNodeId(selectRegistryHero(nextAudit));
  };

  useEffect(() => {
    return () => {
      if (returnMedia?.url.startsWith("blob:")) {
        URL.revokeObjectURL(returnMedia.url);
      }
    };
  }, [returnMedia]);

  useEffect(() => {
    return () => {
      if (pickupMedia?.url.startsWith("blob:")) {
        URL.revokeObjectURL(pickupMedia.url);
      }
    };
  }, [pickupMedia]);

  const handleReturnUpload = async (file: File, url: string) => {
    if (!audit) return;
    if (returnMedia?.url.startsWith("blob:")) {
      URL.revokeObjectURL(returnMedia.url);
    }
    setReturnMedia({
      url,
      type: file.type.startsWith("video/") ? "video" : "image",
      name: file.name,
    });
    const plate = audit.asset_id ?? "AB-123-CD";
    const { audit: nextAudit, detected } = await runReturnInspection(
      plate,
      file,
      audit.audit_id,
      audit
    );
    setAudit(nextAudit);
    setDetectedComponentIds(detected);
    setSelectedNodeId(selectRegistryHero(nextAudit));
  };

  const handleReturnClear = () => {
    if (returnMedia?.url.startsWith("blob:")) {
      URL.revokeObjectURL(returnMedia.url);
    }
    setReturnMedia(null);
    setDetectedComponentIds(null);
  };

  if (!audit) {
    // Deep-linked report still loading; otherwise show the upload-first intake.
    if (auditId) {
      return <div className="loading">Loading audit…</div>;
    }
    return <IntakePanel onRun={handleIntakeRun} />;
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
          pickupMedia={pickupMedia}
          returnMedia={returnMedia}
          onReturnUpload={handleReturnUpload}
          onReturnClear={handleReturnClear}
        />
      </main>
      {lastPatch && <div className="sr-only">Letter generated: {lastPatch.prompt}</div>}
    </div>
  );
}
