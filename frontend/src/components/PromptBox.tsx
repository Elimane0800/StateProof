import { useState } from "react";
import { postFix } from "../api/client";
import type { CursorPatch } from "../types/contract";

interface Props {
  auditId: string;
  nodeId: string;
  onGeneratedPatch: (patch: CursorPatch) => void;
}

export function PromptBox({ auditId, nodeId, onGeneratedPatch }: Props) {
  const [prompt, setPrompt] = useState("");
  const [patch, setPatch] = useState<CursorPatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await postFix(auditId, nodeId, prompt.trim());
      setPatch(result);
      onGeneratedPatch(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate patch.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="promptbox">
      <label>Ask for a fix</label>
      <textarea
        value={prompt}
        placeholder={`e.g. "make this button follow the warning variant instead"`}
        onChange={(e) => setPrompt(e.target.value)}
        rows={2}
      />
      <div className="row">
        <button className="btn btn--primary" onClick={submit} disabled={busy}>
          {busy ? "Generating…" : "Generate patch"}
        </button>
        <span className="hint">Generates a patch — never auto-commits.</span>
      </div>
      {error && <p className="error">{error}</p>}
      {patch && (
        <>
          <pre className="diff">{patch.diff}</pre>
          <button className="btn btn--ghost" onClick={() => navigator.clipboard?.writeText(patch.prompt)}>
            Copy Cursor prompt
          </button>
        </>
      )}
    </section>
  );
}
