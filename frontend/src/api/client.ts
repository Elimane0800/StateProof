import type { AuditPayload, CursorPatch } from "../types/contract";
import mock from "../mocks/audit.json";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

// The Studio is a pure renderer: on any backend error it falls back to the
// frozen mock so the demo never shows a blank screen.
export async function getReport(auditId: string): Promise<AuditPayload> {
  try {
    const res = await fetch(`${API_URL}/report/${encodeURIComponent(auditId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as AuditPayload;
  } catch {
    return mock as AuditPayload;
  }
}

export async function postFix(
  auditId: string,
  nodeId: string,
  prompt: string
): Promise<CursorPatch> {
  const res = await fetch(`${API_URL}/fix`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ audit_id: auditId, node_id: nodeId, prompt }),
  });
  if (!res.ok) throw new Error(`Fix request failed: HTTP ${res.status}`);
  const data = (await res.json()) as { node_id: string; cursor_patch: CursorPatch };
  return data.cursor_patch;
}
