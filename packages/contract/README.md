# SynchronAIse - The JSON Contract

This package is the **frozen source of truth** for the audit payload. One payload drives
everything: the PR comment (R4), the Graph Reconciliation Studio (R5), and the metrics
script (R1/R2).

- [`schema.json`](./schema.json) - JSON Schema (draft-07) of the payload.
- [`contract.example.json`](./contract.example.json) - the canonical example (PR #1).

## Golden rule

Every pair sharing an interface agrees on this contract **before** writing code. It is
copied verbatim into:

- `backend/mocks/audit_mock.json` - R3 serves this from hour one.
- `frontend/src/mocks/audit.json` - R5 designs the Studio against it.

R1 makes the real LLM produce exactly this format; R4 builds the Action against the mock.

## Shape

| Field | Purpose |
| --- | --- |
| `audit_id` | Storage key + Studio route (e.g. `pr-6-run-3`). |
| `pr_number` | The PR being audited. |
| `drift_score` | 0-100, `0` = green/aligned. |
| `screenshot_url` | CI-rendered snapshot; `bbox` annotates it. |
| `design_tree` | Figma intent tree (stable node ids). |
| `code_tree` | Production code AST tree (same node ids). |
| `findings[]` | Violations. Each references a `node_id` (drives coloring) and carries a `cursor_patch`. |
| `ignored_as_noise[]` | The "taste" moment - technical noise deliberately not flagged, with reasoning. |
| `evolution_proposals[]` | Intentional evolution - propose reconciliation, never roll back. |

## Classifications

Every tree node and finding is one of:

- `aligned` - green, matches design intent.
- `design_violation` - red, a real drift from the design system.
- `technical_noise` - grey, ignored on purpose (the judged "taste").
- `intentional_evolution` - amber, new intent to reconcile, not revert.

## Validate

```bash
# from repo root
python backend/scripts/validate_contract.py packages/contract/contract.example.json
```
