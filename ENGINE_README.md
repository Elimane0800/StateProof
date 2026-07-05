> This file is the original engine README (formerly `TheCodeV2`), carried into
> `feat/backend-ai` as a reference for porting into `backend/`
> (see [README.md](README.md) and [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md)).

# ARIA — Agentic condition-report pipeline (4 modules)

Automatic generation of a comparative condition report (entry vs exit), with
legal qualification of damage and a PDF report.

## Architecture

```
Module A (agents/Agent_A) — build_graph   -> entry_graph, exit_graph
                                                 |
Module B (agents/Agent_B) — align         -> list[AlignmentEdge] + confidence_score
                                                 |
Module D (agents/Agent_D) — qualify       -> LegalQualification per "damage" edge
                                                 |
Module C (agents/Agent_C) — build_report  -> rapport.pdf
```

Each arrow is a **data contract** (`agents/common/schemas.py`), not shared
code: each module only knows the *shape* produced by the previous one, never
its internal implementation. The 4 modules can therefore be coded and tested
**in parallel**, each against mocks of the others.

### Module A — Graph construction (`agents/Agent_A`)

Takes images and produces a `Graph` (LPG). Two modes depending on domain:

- **"1 image = 1 checkpoint" mode** (real estate):
  - `prompts.build_state_description_prompt` — one element per image.
  - `nodes.build_node(image, checkpoint_id, room) -> Node` — LLM call +
    pydantic validation + retry + fallback `condition="unknown"`.
  - `graph.build_graph(config, images_by_checkpoint) -> Graph`.
- **"1 image = multiple checkpoints" mode** (vehicle, or any photo showing
  several elements at once):
  - `prompts.build_multi_checkpoint_prompt` — lists all checkpoints expected
    on that image; the VLM responds for each with its own `bbox_pct` location
    in the shared image.
  - `nodes.build_nodes_from_image(image, checkpoints, room) -> list[Node]` —
    ONE VLM call for the entire image (not one per checkpoint), retry at call
    level, per-checkpoint fallback if an element is missing/malformed in the
    response (`visible=False`, `extraction_failed=True`) without affecting
    other checkpoints.
  - `graph.build_graph_from_zone_images(config, images_by_room) -> Graph` —
    `images_by_room` indexed by zone name (e.g. `"exterieur"`, `"interieur"`),
    one image per zone rather than per checkpoint.

In both modes, `Node.bbox_pct` (when available) is used by Module B so two
neighboring checkpoints visible on the same photo are not confused.

### Module B — Detection / alignment (`agents/Agent_B`)

Compares `entry_graph` and `exit_graph` (same node `id`s, by construction).

- `prompts/` — comparison prompt one pair at a time, with few-shot on false
  positives ("technical_noise": sun fading, photo angle).
- `nodes.compare_node(entry_node, exit_node) -> AlignmentEdge`.
- `graph.align(entry_graph, exit_graph) -> list[AlignmentEdge]` — simple loop
  over common `id`s, not graph matching.
- `graph.compute_confidence_score(edges) -> float` — pure function, severity-
  weighted average, shown on the report cover page.

`AlignmentEdge.status` ∈ `{unchanged, normal_wear, damage, evolution}`
(frozen — everything downstream depends on it).

### Module D — Legal qualification (`agents/Agent_D`)

Qualifies a `damage` edge: wear (normal use) vs tenant damage (abnormal use),
based on French decree n°2016-382 of 30/03/2016 and law n°89-462 of 6 July 1989.

- **Mode 1 (deterministic)** — `nodes.apply_vetuste_grid(...)`: if a wear grid
  was annexed to the lease (`config/vetuste_grid.example.json`), pure
  calculation, zero LLM.
- **Mode 2 (legal reasoning)** — `nodes.qualify_with_llm(...)`: default case,
  reasoning by analogy with case-law criteria (occupancy duration, absence of
  repairs, localized vs diffuse defect).
- `graph.qualify(edge, occupancy_months, grid=None) -> LegalQualification`
  chooses the mode automatically based on `grid` presence.

Each `LegalQualification` carries an explicit `disclaimer`, reflected in the
final PDF (not only in JSON).

### Module C — PDF generation (`agents/Agent_C`)

Zero LLM calls: only knows the shape of `AlignmentEdge`/`Node`.

- `nodes.prepare_report_data(...) -> ReportData` — separates data preparation
  (sort by severity, group "unchanged", handle gaps) from rendering.
- `nodes.make_composite_image(...)` — single "entry | exit" image per divergent
  checkpoint (PIL), more robust than two floating images.
- `graph.render_pdf(report_data, output_path)` — pure reportlab rendering,
  testable with mocked data (`python -m agents.Agent_C.graph`).
- `graph.build_report(...)` — full pipeline `prepare_report_data` ->
  composites -> `render_pdf`.

## Installation (uv, Python 3.12)

```bash
uv venv --python 3.12          # creates .venv/ on Python 3.12
uv sync                         # installs dependencies from pyproject.toml (+ uv.lock)
```

`requirements.txt` is regenerated from the lock (`uv export --no-hashes -o requirements.txt`)
and provided only for `pip` compatibility; it is not the source of truth.

Two options for the API key (equivalent; `load_dotenv()` never overwrites a
variable already present in the environment):

```bash
# Option 1 — export in the terminal (valid for the current session)
export NVIDIA_API_KEY="your_key"

# Option 2 — root .env file (persistent; see .env.example)
cp .env.example .env   # then edit .env with the real key
```

## Independent triggers (one per module)

Each module has its own entry point in `scripts/`, to run individually — there
is no automatic run chaining all 4 modules. All work in "smoke test" mode
without real data when possible (A with `--images-dir` absent, C with `--mock`,
D in Mode 1 with the built-in demo); B always requires `NVIDIA_API_KEY`
(`compare_node` always calls the VLM).

```bash
# Module A — graph construction (smoke test if no images provided)
uv run scripts/run_agent_a.py --config config/checkpoints.example.json \
    --images-dir data/appt-12/entry --output entry_graph.json

# Module B — entry/exit alignment (requires NVIDIA_API_KEY)
uv run scripts/run_agent_b.py --entry-graph entry_graph.json \
    --exit-graph exit_graph.json --output edges.json

# Module D — legal qualification (Mode 1 deterministic by default, no API key)
uv run scripts/run_agent_d.py --edge edge.json --occupancy-months 36 \
    --element-category mur --grid config/vetuste_grid.example.json

# Module C — PDF generation (zero LLM; --mock to test without anything else)
uv run scripts/run_agent_c.py --mock --output rapport_mock.pdf
```

See each script header for option details.

## Visual test (Module A + B + divergence watermark)

`AlignmentEdge` carries a `bbox_pct` field: the divergence zone localized by
the VLM, in normalized coordinates `[x_min, y_min, x_max, y_max]` (0 to 1).
`agents/Agent_B/visualize.annotate_divergence` uses it to overlay a very
transparent watermark — **green** on the entry image, **red** on the exit
image — at the exact problem location.

```bash
# 1. Drop two photos of the same checkpoint (see data/test/README.md)
cp your_before_photo.jpg data/test/entry.jpg
cp your_after_photo.jpg data/test/exit.jpg

# 2. Run the test (requires NVIDIA_API_KEY)
uv run scripts/run_visual_test.py

# 3. Result in data/test/annotated/: {checkpoint}_avant.jpg / {checkpoint}_apres.jpg
```

If the VLM cannot localize precisely (`bbox_pct=null`, e.g. `status="unchanged"`
or diffuse change), a simple colored border frames the entire image instead of
a filled zone.

The circle position is NOT taken directly from `bbox_pct` (generalist VLMs
localize roughly): `annotate_divergence` computes a centroid by **classic image
difference** between the two photos (zero LLM, deterministic), isolating the
largest blob of divergent pixels by connected components — filtering ambient
noise (reflections, changing brightness) that fragments into small scattered
patches.

## Full vehicle pipeline (multi-entity, Module A -> B -> D -> C)

Domain where one photo shows **several checkpoints at once** (e.g. vehicle
exterior = bumper + door + fender + wheel + windshield on a single image).
4 photos total: exterior/interior × before/after.

```bash
# 1. Drop your 4 photos (see data/test/vehicule/README.md)
cp entry_ext.jpg data/test/vehicule/entry_exterieur.jpg
cp entry_int.jpg data/test/vehicule/entry_interieur.jpg
cp exit_ext.jpg data/test/vehicule/exit_exterieur.jpg
cp exit_int.jpg data/test/vehicule/exit_interieur.jpg

# 2. Run the full pipeline (requires NVIDIA_API_KEY)
uv run scripts/run_pipeline_vehicule.py
```

Result: `data/test/vehicule/rapport_vehicule.pdf` (Module C) +
`data/test/vehicule/annotated/` (one annotated image pair per detected
divergence, localization preferably based on Module A `bbox_pct` so two
neighboring checkpoints on the same photo are not confused).

```python
from agents.common.schemas import PropertyConfig
from agents.Agent_A.graph import build_graph
from agents.Agent_B.graph import align, compute_confidence_score
from agents.Agent_D.graph import qualify
from agents.Agent_C.graph import build_report

config = PropertyConfig.from_json_file("config/checkpoints.example.json")
entry_graph = build_graph(config, images_by_checkpoint=entry_images)
exit_graph = build_graph(config, images_by_checkpoint=exit_images)

edges = align(entry_graph, exit_graph)
score = compute_confidence_score(edges)

legal = {
    e.node_id: qualify(e, occupancy_months=36)
    for e in edges if e.status == "damage"
}

build_report(entry_graph, exit_graph, edges, score, "rapport.pdf", legal_qualifications=legal)
```

## Structure

```
agents/
  common/schemas.py        # shared data contract between A, B, C, D
  base_model/base_llm_nim.py  # LLM provider (NVIDIA API), text + image support
  Agent_A/  (state.py, prompts/, nodes/, graph.py)  # Module A
  Agent_B/  (state.py, prompts/, nodes/, graph.py)  # Module B
  Agent_C/  (state.py, prompts/, nodes/, graph.py)  # Module C
  Agent_D/  (state.py, prompts/, nodes/, graph.py)  # Module D
config/
  checkpoints.example.json           # checkpoint skeleton, "1 image = 1 checkpoint" mode
  checkpoints_vehicule.example.json  # checkpoint skeleton, multi-entity mode (vehicle)
  vetuste_grid.example.json          # contractual wear grid (Module D, Mode 1)
scripts/
  run_agent_a.py / run_agent_b.py / run_agent_c.py / run_agent_d.py  # independent triggers
  run_visual_test.py          # A+B test with divergence watermark (green/red)
  run_pipeline_vehicule.py    # full A -> B -> D -> C pipeline, vehicle domain (multi-entity)
data/test/
  entry.jpg / exit.jpg        # your two photos to compare (not tracked; see data/test/README.md)
  annotated/                   # annotated images generated by run_visual_test.py
  vehicule/                    # 4 photos + report for vehicle pipeline (see vehicule/README.md)
pyproject.toml / uv.lock       # dependency management (uv, Python 3.12)
```

## Legal disclaimer

Module D produces an **indicative analysis**: it does not replace contradictory
expertise or legal advice. Without a wear grid annexed to the lease,
qualification relies on reasoning by analogy with usual case-law criteria, not
on a statute that would automatically decide the case.
