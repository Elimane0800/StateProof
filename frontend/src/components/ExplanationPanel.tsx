import { useRef, useState } from "react";
import type { AuditPayload, CursorPatch, Classification, Severity } from "../types/contract";
import { CLASS_COLORS } from "./TreeNode";
import { PromptBox } from "./PromptBox";

export interface ReturnMedia {
  url: string;
  type: "image" | "video";
  name: string;
}

interface Props {
  audit: AuditPayload;
  selectedNodeId: string | null;
  onGeneratedPatch: (patch: CursorPatch) => void;
  pickupMedia?: ReturnMedia | null;
  returnMedia: ReturnMedia | null;
  onReturnUpload: (file: File, url: string) => void;
  onReturnClear: () => void;
}

const SEVERITY_COST: Record<Severity, number> = {
  low: 45,
  medium: 120,
  high: 280,
};

const BADGE_LABELS: Record<Classification, string> = {
  design_violation: "Damage",
  technical_noise: "Normal wear — dismissed",
  intentional_evolution: "Agreed change — on file",
  aligned: "No charge",
};

function classificationTag(classification: Classification, extra?: string) {
  const colors = CLASS_COLORS[classification];
  const label = BADGE_LABELS[classification];
  return (
    <span className="tag" style={{ color: colors.border }}>
      ● {label}
      {extra ? ` · ${extra}` : ""}
    </span>
  );
}

const STANDARD_CITATIONS: Record<string, string> = {
  design_violation: "RCAR Fair Wear & Tear Guide §4.2 — new damage vs baseline",
  technical_noise: "BVRLA Fair Wear Standard — acceptable surface wear",
  intentional_evolution: "Rental agreement addendum — change recorded at pickup",
  aligned: "No chargeable difference vs registered baseline",
};

function CopyButton({ text }: { text: string }) {
  return (
    <button className="btn btn--ghost" onClick={() => navigator.clipboard?.writeText(text)}>
      Copy
    </button>
  );
}

function EvidenceFrame({
  label,
  url,
  variant,
  mediaType,
  onUpload,
  onClear,
}: {
  label: string;
  url?: string;
  variant: "pickup" | "return";
  mediaType?: "image" | "video";
  onUpload?: (file: File, url: string) => void;
  onClear?: () => void;
}) {
  const [failed, setFailed] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadable = variant === "return" && !!onUpload;
  const showVideo = mediaType === "video" && !!url;
  const showImage = url && !failed && mediaType !== "video";

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !onUpload) return;
    onUpload(file, URL.createObjectURL(file));
    e.target.value = "";
    setFailed(false);
  };

  const openPicker = () => inputRef.current?.click();

  return (
    <div className="evidence__photo">
      <div className="evidence__photo-head">
        <label>{label}</label>
        {uploadable && url && onClear && (
          <button
            type="button"
            className="btn btn--ghost evidence__clear"
            onClick={(e) => {
              e.stopPropagation();
              onClear();
            }}
          >
            Clear
          </button>
        )}
      </div>
      <div
        className={`evidence__frame evidence__frame--${variant}${uploadable ? " evidence__frame--uploadable" : ""}`}
        onClick={uploadable ? openPicker : undefined}
        onKeyDown={
          uploadable
            ? (e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  openPicker();
                }
              }
            : undefined
        }
        role={uploadable ? "button" : undefined}
        tabIndex={uploadable ? 0 : undefined}
      >
        {showVideo ? (
          <video
            src={url}
            controls
            className="evidence__video"
            onClick={(e) => e.stopPropagation()}
          />
        ) : showImage ? (
          <img src={url} alt={`${label} inspection`} onError={() => setFailed(true)} />
        ) : (
          <div className="evidence__fallback">
            <span className="evidence__fallback-icon">{variant === "pickup" ? "📷" : "🔍"}</span>
            <span className="evidence__fallback-label">
              {uploadable ? "Upload return photo or video" : `${label} inspection`}
            </span>
            <span className="evidence__fallback-hint">
              {uploadable ? "JPEG, PNG, MP4, WebM" : "Vehicle AB-123-CD"}
            </span>
          </div>
        )}
      </div>
      {uploadable && (
        <input
          ref={inputRef}
          type="file"
          accept="image/*,video/*"
          className="sr-only"
          onChange={handleFile}
        />
      )}
    </div>
  );
}

function EvidencePhotos({
  pickupUrl,
  returnUrl,
  pickupMedia,
  returnMedia,
  onReturnUpload,
  onReturnClear,
}: {
  pickupUrl?: string;
  returnUrl: string;
  pickupMedia?: ReturnMedia | null;
  returnMedia: ReturnMedia | null;
  onReturnUpload: (file: File, url: string) => void;
  onReturnClear: () => void;
}) {
  const pickupUrlEffective = pickupMedia?.url ?? (pickupUrl || undefined);
  const pickupLabel = pickupMedia?.type === "video" ? "Pickup video" : "Pickup";
  const returnUrlEffective = returnMedia?.url ?? (returnUrl || undefined);
  const returnLabel = returnMedia?.type === "video" ? "Return video" : "Return photo";

  return (
    <div className="evidence">
      <EvidenceFrame
        label={pickupLabel}
        url={pickupUrlEffective}
        variant="pickup"
        mediaType={pickupMedia?.type}
      />
      <EvidenceFrame
        label={returnLabel}
        url={returnUrlEffective}
        variant="return"
        mediaType={returnMedia?.type}
        onUpload={onReturnUpload}
        onClear={onReturnClear}
      />
    </div>
  );
}

export function ExplanationPanel({
  audit,
  selectedNodeId,
  onGeneratedPatch,
  pickupMedia,
  returnMedia,
  onReturnUpload,
  onReturnClear,
}: Props) {
  const finding = audit.findings.find((f) => f.node_id === selectedNodeId) || null;
  const noise = audit.ignored_as_noise.find((n) => n.node_id === selectedNodeId) || null;
  const evolution = audit.evolution_proposals.find((e) => e.node_id === selectedNodeId) || null;

  const evidenceBlock = (
    <EvidencePhotos
      pickupUrl={audit.pickup_screenshot_url}
      returnUrl={audit.screenshot_url}
      pickupMedia={pickupMedia}
      returnMedia={returnMedia}
      onReturnUpload={onReturnUpload}
      onReturnClear={onReturnClear}
    />
  );

  if (!selectedNodeId) {
    return (
      <aside className="panel">
        {evidenceBlock}
        <div className="panel__empty">
          <h3>Select a body part</h3>
          <p>
            Upload return media to detect visible components, then tap any element in the graph for
            evidence and charge details.
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="panel">
      <header className="panel__head">
        <span className="panel__node">{selectedNodeId}</span>
      </header>

      {evidenceBlock}

      {finding && (
        <section>
          {classificationTag(finding.classification, finding.severity)}
          <div className="kv">
            <div>
              <label>Pickup baseline</label>
              <code>{finding.expected}</code>
            </div>
            <div>
              <label>Return condition</label>
              <code className="bad">{finding.actual}</code>
            </div>
          </div>
          <label>Reasoning</label>
          <p className="reasoning">{finding.reasoning}</p>

          <label>Cited standard</label>
          <p className="reasoning">{STANDARD_CITATIONS[finding.classification]}</p>

          <label>Indicative cost</label>
          <p className="cost">€{SEVERITY_COST[finding.severity]}</p>

          <label>Charge notice draft</label>
          <pre className="diff">{finding.cursor_patch.diff}</pre>
          <div className="row">
            <CopyButton text={finding.cursor_patch.prompt} />
            <span className="hint">Ready to send to renter or desk</span>
          </div>
          <p className="prompt-preview">{finding.cursor_patch.prompt}</p>
        </section>
      )}

      {noise && (
        <section>
          {classificationTag("technical_noise")}
          <label>Reasoning</label>
          <p className="reasoning">{noise.reasoning}</p>
          <label>Cited standard</label>
          <p className="reasoning">{STANDARD_CITATIONS.technical_noise}</p>
          <label>Indicative cost</label>
          <p className="cost cost--zero">€0</p>
        </section>
      )}

      {evolution && (
        <section>
          {classificationTag("intentional_evolution")}
          <label>Reasoning</label>
          <p className="reasoning">{evolution.reasoning}</p>
          <label>Recorded at pickup</label>
          <p className="reasoning">{evolution.proposal}</p>
          <label>Cited standard</label>
          <p className="reasoning">{STANDARD_CITATIONS.intentional_evolution}</p>
          <label>Indicative cost</label>
          <p className="cost cost--zero">€0</p>
        </section>
      )}

      {!finding && !noise && !evolution && (
        <section>
          {classificationTag("aligned")}
          <p className="reasoning">{STANDARD_CITATIONS.aligned}</p>
          <label>Indicative cost</label>
          <p className="cost cost--zero">€0</p>
        </section>
      )}

      <PromptBox
        auditId={audit.audit_id}
        nodeId={selectedNodeId}
        onGeneratedPatch={onGeneratedPatch}
      />
    </aside>
  );
}
