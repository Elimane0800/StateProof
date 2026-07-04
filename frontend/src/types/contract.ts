// Mirrors packages/contract/schema.json. Keep in sync with the backend Pydantic
// models in backend/app/core/schema.py.

export type Classification =
  | "aligned"
  | "design_violation"
  | "technical_noise"
  | "intentional_evolution";

export type Severity = "low" | "medium" | "high";

export interface TreeNode {
  id: string;
  label: string;
  type: string;
  classification: Classification;
  props?: Record<string, unknown>;
  children: TreeNode[];
}

export interface CursorPatch {
  prompt: string;
  diff: string;
}

export interface Finding {
  type: string;
  classification: Classification;
  severity: Severity;
  location: string;
  node_id: string;
  bbox: number[] | null;
  expected: string;
  actual: string;
  reasoning: string;
  cursor_patch: CursorPatch;
}

export interface NoiseItem {
  element: string;
  node_id: string | null;
  reasoning: string;
}

export interface EvolutionProposal {
  element: string;
  node_id: string | null;
  reasoning: string;
  proposal: string;
}

export interface AuditPayload {
  audit_id: string;
  pr_number: number;
  drift_score: number;
  screenshot_url: string;
  design_tree: TreeNode;
  code_tree: TreeNode;
  findings: Finding[];
  ignored_as_noise: NoiseItem[];
  evolution_proposals: EvolutionProposal[];
}
