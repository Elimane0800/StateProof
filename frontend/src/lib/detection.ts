import type { AuditPayload } from "../types/contract";

/** Mock VLM: derive visible components from audit findings, noise, and evolution. */
export function mockDetectComponents(audit: AuditPayload): Set<string> {
  const ids = new Set<string>();
  for (const f of audit.findings) {
    if (f.node_id) ids.add(f.node_id);
  }
  for (const n of audit.ignored_as_noise) {
    if (n.node_id) ids.add(n.node_id);
  }
  for (const e of audit.evolution_proposals) {
    if (e.node_id) ids.add(e.node_id);
  }
  return ids;
}
