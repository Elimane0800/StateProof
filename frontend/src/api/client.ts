import type { AuditPayload, CursorPatch } from "../types/contract";
import mock from "../mocks/audit.json";
import { mockDetectComponents } from "../lib/detection";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

/**
 * Resolve a media URL for display. Backend-served paths (e.g. "/artifacts/..",
 * "/demo/..") are prefixed with the API origin; absolute (http/blob/data) URLs
 * are returned untouched so locally-uploaded blobs and remote images still work.
 */
export function resolveMediaUrl(url?: string | null): string | undefined {
  if (!url) return undefined;
  if (/^(https?:|blob:|data:)/i.test(url)) return url;
  if (url.startsWith("/")) return `${API_URL}${url}`;
  return url;
}

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

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Failed to read file"));
        return;
      }
      const b64 = result.includes(",") ? result.split(",", 2)[1] : result;
      resolve(b64);
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

/** Return inspection: plate + return media → audit (MOCK_MODE uses demo ground-truth). */
export async function postReturnInspection(
  plate: string,
  file: File,
  auditId: string
): Promise<AuditPayload> {
  const screenshot_b64 = await fileToBase64(file);
  const res = await fetch(`${API_URL}/inspection/return`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ asset_id: plate, audit_id: auditId, screenshot_b64 }),
  });
  if (!res.ok) throw new Error(`Return inspection failed: HTTP ${res.status}`);
  return (await res.json()) as AuditPayload;
}

/**
 * First-run inspection from the intake screen: pickup + return media → audit.
 * Falls back to the frozen mock so the demo still renders if the backend is down.
 */
export async function startInspection(
  plate: string,
  pickupFile: File,
  returnFile: File
): Promise<{ audit: AuditPayload; detected: Set<string> }> {
  try {
    const [pickup_b64, screenshot_b64] = await Promise.all([
      fileToBase64(pickupFile),
      fileToBase64(returnFile),
    ]);
    const res = await fetch(`${API_URL}/inspection/return`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ asset_id: plate, pickup_b64, screenshot_b64 }),
    });
    if (!res.ok) throw new Error(`Inspection failed: HTTP ${res.status}`);
    const audit = (await res.json()) as AuditPayload;
    return { audit, detected: mockDetectComponents(audit) };
  } catch {
    const audit = mock as AuditPayload;
    return { audit, detected: mockDetectComponents(audit) };
  }
}

/** Run return inspection when backend is up; otherwise mock detection on current audit. */
export async function runReturnInspection(
  plate: string,
  file: File,
  auditId: string,
  fallbackAudit: AuditPayload
): Promise<{ audit: AuditPayload; detected: Set<string> }> {
  try {
    const audit = await postReturnInspection(plate, file, auditId);
    return { audit, detected: mockDetectComponents(audit) };
  } catch {
    return { audit: fallbackAudit, detected: mockDetectComponents(fallbackAudit) };
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
