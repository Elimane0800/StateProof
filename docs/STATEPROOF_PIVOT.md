# StateProof — 10-Hour Pivot Plan (Car-First)

> **StateProof** — *"Proof of how it was."*
> Pivot of SynchronAIse from UI-drift auditing to a real-world, day-to-day problem:
> **damage disputes on things you hand back** — scoped to ONE feasible vertical for the
> hackathon: rental cars. Same engine, same taxonomy, same Studio — new graphs.

## The pitch

Everyone has stood at a rental-car return desk being shown a scratch they're sure was
already there. Surprise damage charges are the #1 car-rental complaint worldwide — and
the same "damage vs wear vs already-agreed" fight covers everything humans hand back:
apartments and deposits, leased equipment, Airbnbs, offices.

Every one of these disputes hinges on a three-way judgment call — and that judgment is
literally our Taste Engine's taxonomy:

| Dispute question | Domain class | Existing engine class |
|---|---|---|
| Is it damage? (renter liable) | `damage` | `design_violation` |
| Is it normal wear? (cannot be charged) | `normal_wear` | `technical_noise` |
| Was it an agreed change? (approval on file) | `agreed_change` | `intentional_evolution` |

**How it works:** photograph the car at pickup → VLM fills a fixed condition checklist
(the baseline). Photograph again at return → the return graph. The engine diffs them,
classifies every difference with visible reasoning and cited wear-and-tear standards,
and produces an itemized **StateProof Report**, a **Damage Charge Score** (€ at stake),
and a one-click **dispute letter** / **charge notice** via `/fix`.

**The Asset Registry (the ledger layer):** conditions are keyed to the **license
plate**, not the contract. Every event (pickup, renewal, return) appends a sealed
snapshot to the asset's timeline, and each audit diffs against the *registered*
baseline — so a pre-existing scratch can never be charged twice. The VLM reads the
plate straight off the photo and auto-links the audit to its asset.

## Feasibility decisions (why this fits in 10 hours)

- **One vertical: cars.** The broad multi-asset version dies on *graph alignment*:
  free-form photos of a room produce differently-structured graphs (the UI version had
  deterministic `data-node` IDs; photos don't), and general photo-to-graph matching is
  a research problem.
- **Fixed element checklist.** The VLM does not invent the graph — it fills a fixed car
  schema (front bumper, hood, windshield, four doors/panels, wheels, rear) with
  per-element condition and defects. Pickup and return graphs align **by construction**,
  so the existing diff engine works unchanged.
- **Apartments are story, not build.** One seeded MOCK apartment audit shows the
  multi-vertical vision without a second live pipeline. Arbitrary rooms have no clean
  checklist — solved post-hackathon with per-asset-class templates.

## What survives from the current codebase (~75%)

- **JSON contract shape** (`backend/app/core/schema.py`, `frontend/src/types/contract.ts`)
  — the three classification classes keep their semantics, gain domain aliases
- **FastAPI routes** `POST /audit`, `GET /report/{id}`, `POST /fix` (`backend/app/api/`)
- **Classifier chain** Gemini → OpenAI → heuristic (`backend/app/services/classifier.py`,
  `vlm.py`) — the VLM becomes the star: it reads photos
- **Studio**: dual react-flow trees, node coloring, explanation panel, score
  (`frontend/src/components/Studio.tsx`)
- **MOCK_MODE** + seeded audits, so the demo cannot die on stage

## The 10 hours

### Hour 0–1: Domain vocabulary + branding

- Schema: fixed car element types (`front_bumper`, `hood`, `windshield`, `door_fl/fr/rl/rr`,
  `wheel_*`, `rear`); props `condition`, `defects[]` (type, location, size)
- Every audit carries `asset_id` (plate) + `contract_event` (`pickup` / `renewal` / `return`)
- Classification labels aliased: `damage` / `normal_wear` / `agreed_change`
- Drift score → **Damage Charge Score** (estimated € at stake)
- Branding: product name **StateProof** (tagline *"Proof of how it was."*) in the Studio
  header, FastAPI title, and README; report output titled "StateProof Report";
  "Design intent" → "Pickup baseline", "Implemented UI" → "Return state"

### Hour 1–3: Demo dataset (one car, four disputes)

One vehicle with a visible license plate, pickup + return photo sets (real phone photos
preferred, consistent angle per checklist element). Four cases in
`synchronaise-demo/ground-truth/`:

1. New dent on the door → **damage** (charge justified, cost estimate)
2. Scratch registered at pickup → **not chargeable** — the registry moment, the
   emotional core of the demo
3. Dirt / stone-chip dust → **normal_wear**, dismissed with visible reasoning
4. Tire replaced with the company's approval on file → **agreed_change**

Author the matching condition-graph JSONs as seeded MOCK ground truth, plus one seeded
apartment audit for the second-act story.

### Hour 3–5.5: Backend swap

- `figma_parser.py` → `baseline_parser.py`, `code_parser.py` → `return_parser.py`: both
  send photos + the fixed checklist schema to the VLM and get back a filled condition
  graph plus any visible plate; mock path loads the authored JSONs
- Rewrite `classification.md`: damage vs fair-wear taxonomy grounded in rental-industry
  wear-and-tear standards (scratch-length thresholds, chip counts); require a standard
  citation + estimated cost per finding
- Update heuristic fallback rules so MOCK_MODE stays coherent; re-seed mocks

### Hour 5.5–6.5: Asset Registry (thin)

- `storage.py`: in-memory assets keyed by plate holding `{ baseline, audit_timeline[] }`;
  `GET /assets/{id}`
- `POST /audit` without an explicit `asset_id` auto-links via the recognized plate and
  diffs against the registered baseline
- Seed the demo car as a registered asset with history

### Hour 6.5–8: Studio reskin

- StateProof branding in the header; panels: "Pickup" vs "Return" (`Studio.tsx`,
  `GraphView.tsx`)
- `DriftScore.tsx` → Damage Charge Score in €
- Asset header: plate + event timeline (display only)
- `ExplanationPanel.tsx`: side-by-side photo evidence, reasoning, cited standard, cost
- `PromptBox.tsx` → "Generate dispute letter" / "Generate charge notice" via `/fix`

### Hour 8–10: Live demo + pitch

- The live on-stage run: photograph the car → VLM reads the plate → registry pulls the
  pickup baseline → StateProof Report shows the pre-existing scratch is **not
  chargeable**. Everything else runs seeded
- README/pitch: rental-dispute pain, the wear-vs-damage taste story, the ledger framing
  ("the asset owns its history"), roadmap slide (apartments/deposits via checklist
  templates, equipment leasing, Airbnb, insurance claims)
- Dry-run the loop twice; keep the current UI-auditor demo on a branch as fallback

## Explicitly cut (10-hour reality)

- Apartment live pipeline — seeded mock + roadmap only (no clean checklist for
  arbitrary rooms yet)
- GitHub Action (irrelevant here; hidden, not deleted)
- User accounts, upload persistence, payments — single-session demo flow
- Cost-estimation accuracy — flat per-category estimates labeled "indicative"
- Rebaseline-on-renewal endpoint — only if time remains; timeline click-to-diff cut
- Registry persistence beyond in-memory + seeded JSON — a real DB is post-hackathon

## Todos

- [ ] **vocab-reframe** — Fixed car element checklist in schema + contract, damage /
      normal_wear / agreed_change aliases, Damage Charge Score, asset_id +
      contract_event, StateProof branding
- [ ] **demo-dataset** — One-car dataset: pickup + return photos with visible plate,
      4 dispute cases + authored condition-graph JSONs, one seeded apartment mock
- [ ] **backend-parsers** — Checklist-driven VLM extractors (`baseline_parser` /
      `return_parser`) with plate extraction and mock JSON path
- [ ] **asset-registry** — Thin plate-keyed registry: baseline + audit timeline,
      auto-link audits via recognized plate, `GET /assets/{id}`
- [ ] **classifier-prompt** — Damage vs fair-wear taxonomy with industry standards,
      citation + cost estimate per finding
- [ ] **studio-reskin** — StateProof header, Pickup vs Return panels, Damage Charge
      Score in €, asset header with plate + timeline, photo evidence panel,
      dispute-letter prompt box
- [ ] **live-vlm** — Live run: car photo → plate read → registry baseline →
      "pre-existing scratch not chargeable"
- [ ] **pitch-harden** — README/pitch rewrite, seed apartment second-act, dry-run twice
