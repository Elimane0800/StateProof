import { useState } from "react";
import { postFix } from "../api/client";
import type { CursorPatch } from "../types/contract";

type LetterMode = "dispute" | "charge";

interface Props {
  auditId: string;
  nodeId: string;
  onGeneratedPatch: (patch: CursorPatch) => void;
}

const MODE_LABELS: Record<LetterMode, { label: string; placeholder: string; prefix: string }> = {
  dispute: {
    label: "Generate dispute letter",
    placeholder: 'e.g. "Scratch was visible at pickup — cite baseline photos and dismiss the charge"',
    prefix: "Generate a dispute letter for the renter:",
  },
  charge: {
    label: "Generate charge notice",
    placeholder: 'e.g. "Document new bumper scratch with cited standard and €280 repair estimate"',
    prefix: "Generate a damage charge notice for the rental desk:",
  },
};

export function PromptBox({ auditId, nodeId, onGeneratedPatch }: Props) {
  const [prompt, setPrompt] = useState("");
  const [patch, setPatch] = useState<CursorPatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<LetterMode | null>(null);

  const submit = async (letterMode: LetterMode) => {
    if (!prompt.trim()) return;
    setMode(letterMode);
    setBusy(true);
    setError(null);
    const fullPrompt = `${MODE_LABELS[letterMode].prefix} ${prompt.trim()}`;
    try {
      const result = await postFix(auditId, nodeId, fullPrompt);
      setPatch(result);
      onGeneratedPatch(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate letter.");
    } finally {
      setBusy(false);
    }
  };

  const activeMode = mode ?? "dispute";

  return (
    <section className="promptbox">
      <label>Resolution</label>
      <textarea
        value={prompt}
        placeholder={MODE_LABELS.dispute.placeholder}
        onChange={(e) => setPrompt(e.target.value)}
        rows={2}
      />
      <div className="row promptbox__actions">
        <button
          className="btn btn--primary"
          onClick={() => submit("dispute")}
          disabled={busy}
        >
          {busy && mode === "dispute" ? "Generating…" : MODE_LABELS.dispute.label}
        </button>
        <button
          className="btn btn--ghost"
          onClick={() => submit("charge")}
          disabled={busy}
        >
          {busy && mode === "charge" ? "Generating…" : MODE_LABELS.charge.label}
        </button>
      </div>
      <span className="hint">Draft only — review before sending to renter or desk.</span>
      {error && <p className="error">{error}</p>}
      {patch && (
        <>
          <label>{activeMode === "dispute" ? "Dispute letter" : "Charge notice"}</label>
          <pre className="diff">{patch.diff}</pre>
          <button className="btn btn--ghost" onClick={() => navigator.clipboard?.writeText(patch.prompt)}>
            Copy letter
          </button>
        </>
      )}
    </section>
  );
}
