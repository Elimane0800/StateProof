# StateProof demo ground truth

Authoritative fixtures for the hackathon live demo and MOCK_MODE backend loader.

## Plate

**AB-123-CD** — VW Golf, silver. All scenarios use this plate so the registry hero (`door_fl`) resolves consistently with the Studio mock.

## Files

| File | Scenario | Classification |
|------|----------|----------------|
| `pickup-baseline.json` | Pickup inspection baseline | — |
| `return-audit.json` | Full return audit (fixture) | mixed |
| `scenarios/d4-new-dent-damage.json` | New dent on `door_fr` | `damage` |
| `scenarios/d5-registered-scratch.json` | Pre-logged scratch on `door_fl` | **not chargeable** |
| `scenarios/d6-stone-chip-normal-wear.json` | Stone-chip dust on `front_bumper` | `normal_wear` |
| `scenarios/d7-tire-swap-agreed-change.json` | Declared roof box on `rear` | `agreed_change` |
| `registry/AB-123-CD.json` | Plate-keyed ledger | baseline + audits |

## Photos

See `photos/README.md`. Drop real pickup/return shots into `photos/pickup/` and `photos/return/`. Placeholder PNGs are included so paths resolve offline.

## Live demo path

1. **Live return inspection** — upload return photo in Studio (or Intake) → `POST /inspection/return` with plate **AB-123-CD**. The backend runs the live ARIA pipeline via `aria_adapter` (Modules A → B → D); **`NVIDIA_API_KEY` is required** — there is no mock fallback on this route.
2. **Fixture report (offline)** — with `MOCK_MODE=1`, `GET /report/{id}` serves JSON from this folder via `demo_loader`.
3. **Frontend fallback** — if the API is down or errors, the Studio loads `frontend/src/mocks/audit.json` so the UI still renders.
4. **Hero case** — select **door_fl** in the graph → panel shows registry reasoning → **€0 / not chargeable**.
