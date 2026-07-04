import type { AuditPayload, CursorPatch } from "../types/contract";
import { CLASS_COLORS } from "./TreeNode";
import { PromptBox } from "./PromptBox";

interface Props {
  audit: AuditPayload;
  selectedNodeId: string | null;
  onGeneratedPatch: (patch: CursorPatch) => void;
}

function CopyButton({ text }: { text: string }) {
  return (
    <button className="btn btn--ghost" onClick={() => navigator.clipboard?.writeText(text)}>
      Copy
    </button>
  );
}

export function ExplanationPanel({ audit, selectedNodeId, onGeneratedPatch }: Props) {
  const finding = audit.findings.find((f) => f.node_id === selectedNodeId) || null;
  const noise = audit.ignored_as_noise.find((n) => n.node_id === selectedNodeId) || null;
  const evolution = audit.evolution_proposals.find((e) => e.node_id === selectedNodeId) || null;

  if (!selectedNodeId) {
    return (
      <aside className="panel">
        <div className="panel__empty">
          <h3>Select a node</h3>
          <p>Click any node in the graph to see the AI reasoning and its Cursor patch.</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="panel">
      <header className="panel__head">
        <span className="panel__node">{selectedNodeId}</span>
      </header>

      {finding && (
        <section>
          <span className="tag" style={{ color: CLASS_COLORS.design_violation.border }}>
            ● Design violation · {finding.severity}
          </span>
          <div className="kv">
            <div>
              <label>Expected</label>
              <code>{finding.expected}</code>
            </div>
            <div>
              <label>Actual</label>
              <code className="bad">{finding.actual}</code>
            </div>
          </div>
          <label>Reasoning</label>
          <p className="reasoning">{finding.reasoning}</p>

          <label>Cursor patch</label>
          <pre className="diff">{finding.cursor_patch.diff}</pre>
          <div className="row">
            <CopyButton text={finding.cursor_patch.prompt} />
            <span className="hint">Paste into Cursor (Cmd+K)</span>
          </div>
          <p className="prompt-preview">{finding.cursor_patch.prompt}</p>
        </section>
      )}

      {noise && (
        <section>
          <span className="tag" style={{ color: CLASS_COLORS.technical_noise.border }}>
            ● Ignored as technical noise
          </span>
          <p className="reasoning">{noise.reasoning}</p>
        </section>
      )}

      {evolution && (
        <section>
          <span className="tag" style={{ color: CLASS_COLORS.intentional_evolution.border }}>
            ● Intentional evolution
          </span>
          <p className="reasoning">{evolution.reasoning}</p>
          <label>Proposal</label>
          <p className="reasoning">{evolution.proposal}</p>
        </section>
      )}

      {!finding && !noise && !evolution && (
        <section>
          <span className="tag" style={{ color: CLASS_COLORS.aligned.border }}>
            ● Aligned
          </span>
          <p className="reasoning">This node matches the design intent. No action needed.</p>
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
