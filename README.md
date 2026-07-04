# StateProof

> **StateProof** — *"Proof of how it was."*
> AI condition auditing for everything you hand back. Built on the SynchronAIse
> drift-audit engine (RAISE Hackathon 2026, Cursor Track).

## The problem

Everyone has stood at a rental-car return desk being shown a scratch they're sure was
already there. Surprise damage charges are the #1 car-rental complaint worldwide — and
the same "damage vs wear vs already-agreed" fight covers everything humans hand back:
apartments and deposits, leased equipment, Airbnbs, offices.

Every one of these disputes hinges on a three-way judgment call. That judgment is
exactly what our Taste Engine classifies:

| Dispute question | StateProof class | Engine class (SynchronAIse) |
|---|---|---|
| Is it damage? (renter liable) | `damage` | `design_violation` |
| Is it normal wear? (cannot be charged) | `normal_wear` | `technical_noise` |
| Was it an agreed change? (approval on file) | `agreed_change` | `intentional_evolution` |

The `normal_wear` class is the differentiator: a dumb scanner flags every pixel
difference; StateProof explains *why* the stone-chip dust is not chargeable — with the
wear-and-tear standard cited.

## How it works

1. **Pickup:** photograph the car → the VLM fills a **fixed condition checklist**
   (front bumper, hood, windshield, doors, wheels, rear) → the baseline graph.
2. **Return:** photograph again → the return graph. Fixed checklist means both graphs
   align by construction — the diff engine works unchanged.
3. **Audit:** the engine diffs the graphs and classifies every difference with visible
   reasoning, a cited standard, and an indicative cost.
4. **Output:** an itemized **StateProof Report**, a **Damage Charge Score** (€ at
   stake), and a one-click **dispute letter** / **charge notice**.

**The Asset Registry:** conditions are keyed to the **license plate**, not the
contract. Every event (pickup, return) appends a sealed snapshot, and each audit diffs
against the *registered* baseline — so a pre-existing scratch can never be charged
twice. The VLM reads the plate straight off the photo and auto-links the audit.

## Architecture (inherited from SynchronAIse)

- **Contract** — shared JSON payload driving backend, Studio, and metrics
- **Backend** — FastAPI (`POST /audit`, `GET /report/{id}`, `POST /fix`), classifier
  fallback chain Gemini → OpenAI → deterministic heuristic, MOCK_MODE for offline demos
- **Studio** — React + react-flow dual-graph viewer: Pickup vs Return, node coloring by
  classification, evidence panel, Damage Charge Score
- **Demo data** — one car, four dispute cases (new dent, pre-registered scratch, wear
  dust, approved tire swap) with authored ground-truth graphs

## Roadmap

- Apartments & deposits via per-asset-class checklist templates
- Equipment leasing, Airbnb, insurance claims — "everything humans hand back"
- Persistent registry (real DB), rebaseline-on-renewal, timeline diffing
- Photogrammetry / LiDAR capture beyond single photos

## Build

See [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) for the 4-hour team build plan and task
assignments.
