# Vehicle pipeline test (Module A → B → D → C)

Drop your 4 photos here (one per zone × state):

| Expected file | Content |
|---------------|---------|
| `entry_exterieur.jpg` | Vehicle exterior at entry (bumper, door, fender, wheel, windshield visible) |
| `entry_interieur.jpg` | Vehicle interior at entry (driver seat, steering wheel, dashboard, floor) |
| `exit_exterieur.jpg` | Same exterior framing at exit |
| `exit_interieur.jpg` | Same interior framing at exit |

Each photo can (and should) show **multiple checkpoints at once** — unlike real-estate mode (1 photo = 1 checkpoint), Module A identifies all elements listed in `config/checkpoints_vehicule.example.json` in a single call per photo.

## Run the full pipeline

```bash
export NVIDIA_API_KEY=...   # or in a root .env file
uv run scripts/run_pipeline_vehicule.py
```

The script:
1. Builds entry/exit graphs (Module A, 2 VLM calls total).
2. Compares each common checkpoint (Module B).
3. Generates annotated images (localized circle) for each divergence, in `annotated/`.
4. Legally qualifies each divergence (Module D).
5. Generates the final report in `rapport_vehicule.pdf` (Module C).

## Reference ground truth (for evaluating results)

| checkpoint_id | Injected defect | Expected class |
|---------------|-----------------|----------------|
| `pare_choc_avant` | micro clear-coat scratch | `damage` (low severity) |
| `portiere_avant_gauche` | light barely visible dent | `damage` |
| `aile_avant_droite` | unchanged | `unchanged` |
| `jante_avant_gauche` | rim edge scuff | `damage` |
| `pare_brise` | 3mm chip impact | `damage` (ambiguous — prior existence should be flagged as uncertain) |
| `siege_conducteur` | diffuse sag/discoloration | `normal_wear` |
| `volant` | unchanged | `unchanged` |
| `tableau_de_bord` | micro screen scratch | `damage` (low severity) |
| `plancher_conducteur` | diffuse stain | `damage` or abnormal use depending on context (good Module D test) |

Note: on very subtle defects, an image generation/editing tool may ignore or exaggerate them. If the injected defect is not visible to the naked eye on your photo, the pipeline will not detect it either — that is not a pipeline bug.
