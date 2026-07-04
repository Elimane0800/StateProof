# StateProof

> **StateProof** ÔÇö *"Proof of how it was."*
> AI condition auditing for everything you hand back. Built on the SynchronAIse
> drift-audit engine (RAISE Hackathon 2026, Cursor Track).

## The problem

Everyone has stood at a rental-car return desk being shown a scratch they're sure was
already there. Surprise damage charges are the #1 car-rental complaint worldwide ÔÇö and
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
difference; StateProof explains *why* the stone-chip dust is not chargeable ÔÇö with the
wear-and-tear standard cited.

## How it works

1. **Pickup:** photograph the car ÔåÆ the VLM fills a **fixed condition checklist**
   (front bumper, hood, windshield, doors, wheels, rear) ÔåÆ the baseline graph.
2. **Return:** photograph again ÔåÆ the return graph. Fixed checklist means both graphs
   align by construction ÔÇö the diff engine works unchanged.
3. **Audit:** the engine diffs the graphs and classifies every difference with visible
   reasoning, a cited standard, and an indicative cost.
4. **Output:** an itemized **StateProof Report**, a **Damage Charge Score** (Ôé¼ at
   stake), and a one-click **dispute letter** / **charge notice**.

**The Asset Registry:** conditions are keyed to the **license plate**, not the
contract. Every event (pickup, return) appends a sealed snapshot, and each audit diffs
against the *registered* baseline ÔÇö so a pre-existing scratch can never be charged
twice. The VLM reads the plate straight off the photo and auto-links the audit.

## Architecture (inherited from SynchronAIse)

- **Contract** ÔÇö shared JSON payload driving backend, Studio, and metrics
- **Backend** ÔÇö FastAPI (`POST /audit`, `GET /report/{id}`, `POST /fix`), classifier
  fallback chain Gemini ÔåÆ OpenAI ÔåÆ deterministic heuristic, MOCK_MODE for offline demos
- **Studio** ÔÇö React + react-flow dual-graph viewer: Pickup vs Return, node coloring by
  classification, evidence panel, Damage Charge Score
- **Demo data** ÔÇö one car, four dispute cases (new dent, pre-registered scratch, wear
  dust, approved tire swap) with authored ground-truth graphs

## Roadmap

- Apartments & deposits via per-asset-class checklist templates
- Equipment leasing, Airbnb, insurance claims ÔÇö "everything humans hand back"
- Persistent registry (real DB), rebaseline-on-renewal, timeline diffing
- Photogrammetry / LiDAR capture beyond single photos

## Team plan

Five people, three tracks: **Backend (2)**, **Frontend (1)**, **Demo + integration (2)**.
Everyone works against the same JSON contract so tracks can run in parallel.

**Coordination rule:** freeze the shared schema by **T+1:00**. If it changes, all five
people must know immediately. **Only the Integrator merges to `main`.**

| Person | Track | Branch | Primary deliverable |
|--------|-------|--------|---------------------|
| _assign_ | Integration | `feat/integration` | Port SynchronAIse, keep `main` green, wire live demo |
| _assign_ | Backend ÔÇö API | `feat/backend-api` | Parsers, registry, `/audit` routes |
| _assign_ | Backend ÔÇö AI | `feat/backend-ai` | Schema, classifier, VLM/NIM chain |
| _assign_ | Frontend | `feat/frontend` | Studio re-skin (Pickup / Return UI) |
| _assign_ | Demo + deploy | `feat/demo` / `feat/deploy-k3s` | Car photos, ground-truth JSONs, k3s stretch |

Full timeline and git rules: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

**Hard rule:** feature freeze at **T+3:00**. Pitch and rehearsal are **tomorrow morning**.

---

## Backend track (2 people)

Everything under `backend/` and `packages/contract/`. Frontend must not edit these
paths; it only consumes types from `frontend/src/types/contract.ts`.

### Backend ÔÇö AI & schema

**Branch:** `feat/backend-ai` ┬À **Critical path ÔÇö schema on `main` by T+1:00**

| Task | File(s) |
|------|---------|
| Car element types (`front_bumper`, `hood`, `windshield`, doors, wheels, `rear`) | `backend/app/core/schema.py` |
| Audit fields: `asset_id` (plate), `contract_event` (`pickup` / `return`) | `backend/app/core/schema.py` |
| Classification aliases: `damage`, `normal_wear`, `agreed_change` | `backend/app/core/schema.py` |
| Wear-and-tear taxonomy prompt (scratch thresholds, chip counts) | `backend/**/classification.md` |
| Heuristic fallback so MOCK_MODE stays coherent | `backend/app/services/classifier.py` |
| NVIDIA NIM as first provider, then Gemini ÔåÆ OpenAI ÔåÆ heuristic | `backend/app/services/vlm.py`, `config.py` |

**Do not touch:** parsers, `storage.py` registry, `frontend/`.

**Also deliver:** mirror types in `frontend/src/types/contract.ts` (or hand off to
Frontend once stable ÔÇö agree at kickoff).

---

### Backend ÔÇö API & registry

**Branch:** `feat/backend-api` ┬À **Mock path T+2:00, live VLM T+3:00**

| Task | File(s) |
|------|---------|
| Pickup parser (VLM fills checklist from photos) | `baseline_parser.py` (was `figma_parser.py`) |
| Return parser | `return_parser.py` (was `code_parser.py`) |
| License plate extraction from photos | parsers + `vlm.py` prompt |
| Mock path loading JSONs from demo folder | parsers |
| Plate-keyed Asset Registry | `backend/app/services/storage.py` |
| Auto-link audit when plate recognized | `POST /audit` route |
| Keep `/report/{id}`, `/fix`, `/health` working | `backend/app/api/` |

**Do not touch:** `schema.py`, classifier heuristic, `frontend/`, `demo/` photos.

**Depends on:** schema from Backend ÔÇö AI (T+1:00), JSONs from Demo track (T+2:00).

---

## Frontend track (1 person)

Everything under `frontend/src/`. Work from seeded mocks ÔÇö you only need stable
TypeScript types, not a live backend.

**Branch:** `feat/frontend` ┬À **Done by T+3:00**

| Task | File(s) |
|------|---------|
| StateProof branding + tagline in header | `App.tsx`, `Studio.tsx` |
| Relabel panels: **Pickup** vs **Return** | `Studio.tsx`, `GraphView.tsx` |
| Drift score ÔåÆ **Damage Charge Score** (Ôé¼) | `DriftScore.tsx` |
| License plate in asset header | `Studio.tsx` |
| Photo evidence, reasoning, standard, cost | `ExplanationPanel.tsx` |
| "Generate dispute letter" / "Generate charge notice" | `PromptBox.tsx` |
| Consume updated types | `frontend/src/types/contract.ts` |

**Do not touch:** `backend/`, `packages/contract/`, `demo/`.

**Depends on:** `contract.ts` from Backend ÔÇö AI (T+1:00).

---

## Demo + deploy track (1 person)

Photos and ground truth. Minimal application code.

**Branch:** `feat/demo` ┬À **JSONs ready by T+2:00**

| Task | Output |
|------|--------|
| Pickup + return photo sets, plate visible, consistent angles | `demo/ground-truth/photos/` |
| Pre-existing scratch pair (live demo case) | same |
| Ground-truth JSON ÔÇö new dent ÔåÆ `damage` | `demo/ground-truth/` |
| Ground-truth JSON ÔÇö registered scratch ÔåÆ not chargeable | same |
| Ground-truth JSON ÔÇö stone-chip dust ÔåÆ `normal_wear` | same |
| Ground-truth JSON ÔÇö approved tire swap ÔåÆ `agreed_change` | same |

**Stretch (T+3:00 only, branch `feat/deploy-k3s`):** port Helm chart + deploy scripts
from SynchronAIse, rename to `stateproof`. Only if live VLM works; otherwise skip.

**Do not touch:** `backend/`, `frontend/`, `packages/`.

**Depends on:** schema shape from Backend ÔÇö AI (T+1:00).

---

## Integration track (1 person)

**Branch:** `feat/integration` first, then merge all lanes to `main`.

| When | Task |
|------|------|
| **T+0:00ÔÇô0:30** | Port `packages/contract/`, `backend/`, `frontend/` from SynchronAIse. MOCK_MODE green. **Merge to `main` within 30 min.** |
| **T+0:30ÔÇô3:00** | Merge backend + frontend + demo branches; resolve conflicts; smoke after each merge |
| **T+3:00** | Wire live demo: photo ÔåÆ plate ÔåÆ registry ÔåÆ "scratch not chargeable" |
| **T+3:30ÔÇô4:00** | End-to-end smoke test; tag clean commit |

You are the **only person who merges to `main`** during the build.

---

## Quick start

```powershell
git fetch origin
git checkout main
git pull

# Integrator first:
git checkout feat/integration

# Everyone else, after bootstrap is on main:
git checkout feat/<track-branch>   # integration | backend-ai | backend-api | frontend | demo
git rebase main
```

**Backend env** (`backend/.env`): at least one of `NVIDIA_API_KEY`, `GEMINI_API_KEY`,
`OPENAI_API_KEY` (MOCK_MODE works with zero keys).

**Frontend env:** `npm install` in `frontend/`, then `npm run dev`.



## Moteur source (engine)

Le code Python a la racine de cette branche (`agents/`, `scripts/`, `config/`) est le
**moteur d'origine** (pipeline agentique A/B/C/D, `bbox_pct`, detection multi-entites,
annotation par difference de pixels) a porter/adapter dans `backend/` selon le plan
ci-dessus. Details complets : [ENGINE_README.md](ENGINE_README.md).
