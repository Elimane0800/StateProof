# ARIA — Pipeline agentique état des lieux (4 modules)

Génération automatique d'un constat d'état des lieux comparatif (entrée vs
sortie), avec qualification légale des dégradations et rapport PDF.

## Architecture

```
Module A (agents/Agent_A) — build_graph   -> entry_graph, exit_graph
                                                 |
Module B (agents/Agent_B) — align         -> list[AlignmentEdge] + confidence_score
                                                 |
Module D (agents/Agent_D) — qualify       -> LegalQualification par écart "damage"
                                                 |
Module C (agents/Agent_C) — build_report  -> rapport.pdf
```

Chaque flèche est un **contrat de données** (`agents/common/schemas.py`), pas
du code partagé : chaque module ne connaît que la *forme* produite par le
précédent, jamais son implémentation interne. Les 4 modules sont donc
codables et testables **en parallèle**, chacun contre des mocks des autres.

### Module A — Construction du graphe (`agents/Agent_A`)

Prend des images et produit un `Graph` (LPG). Deux modes selon le domaine :

- **Mode "1 image = 1 checkpoint"** (immobilier) :
  - `prompts.build_state_description_prompt` — un seul élément par image.
  - `nodes.build_node(image, checkpoint_id, room) -> Node` — appel LLM +
    validation pydantic + retry + fallback `condition="unknown"`.
  - `graph.build_graph(config, images_by_checkpoint) -> Graph`.
- **Mode "1 image = plusieurs checkpoints"** (véhicule, ou toute photo
  montrant plusieurs éléments à la fois) :
  - `prompts.build_multi_checkpoint_prompt` — liste tous les checkpoints
    attendus sur cette image ; le VLM répond pour chacun, avec sa propre
    `bbox_pct` de localisation dans l'image partagée.
  - `nodes.build_nodes_from_image(image, checkpoints, room) -> list[Node]` —
    UN SEUL appel VLM pour toute l'image (pas un par checkpoint), retry au
    niveau de l'appel, fallback par checkpoint individuel si un élément
    manque/est mal formé dans la réponse (`visible=False`,
    `extraction_failed=True`), sans affecter les autres checkpoints.
  - `graph.build_graph_from_zone_images(config, images_by_room) -> Graph` —
    `images_by_room` indexé par nom de zone (ex: `"exterieur"`,
    `"interieur"`), une image par zone plutôt que par checkpoint.

Dans les deux modes, `Node.bbox_pct` (quand disponible) sert ensuite au
Module B pour ne pas confondre deux checkpoints voisins visibles sur la
même photo.

### Module B — Détection / alignement (`agents/Agent_B`)

Compare `entry_graph` et `exit_graph` (mêmes `id` de nœuds, par construction).

- `prompts/` — prompt de comparaison une paire à la fois, avec few-shot sur
  les faux positifs ("technical_noise" : décoloration solaire, angle photo).
- `nodes.compare_node(entry_node, exit_node) -> AlignmentEdge`.
- `graph.align(entry_graph, exit_graph) -> list[AlignmentEdge]` — simple
  boucle sur les `id` communs, pas de matching de graphe.
- `graph.compute_confidence_score(edges) -> float` — fonction pure, moyenne
  pondérée par sévérité, affichée en page de garde du rapport.

`AlignmentEdge.status` ∈ `{unchanged, normal_wear, damage, evolution}`
(figé — tout en dépend en aval).

### Module D — Qualification légale (`agents/Agent_D`)

Qualifie un écart `damage` : vétusté (usage normal) vs dégradation locative
(usage anormal), en s'appuyant sur le décret n°2016-382 du 30/03/2016 et la
loi n°89-462 du 6 juillet 1989.

- **Mode 1 (déterministe)** — `nodes.apply_vetuste_grid(...)` : si une grille
  de vétusté a été annexée au bail (`config/vetuste_grid.example.json`),
  calcul pur, zéro LLM.
- **Mode 2 (raisonnement légal)** — `nodes.qualify_with_llm(...)` : cas par
  défaut, raisonnement par analogie avec les critères jurisprudentiels
  (durée d'occupation, absence de travaux, défaut localisé vs diffus).
- `graph.qualify(edge, occupancy_months, grid=None) -> LegalQualification`
  choisit le mode automatiquement selon la présence de `grid`.

Chaque `LegalQualification` porte un `disclaimer` explicite, répercuté dans
le PDF final (pas seulement dans le JSON).

### Module C — Génération du PDF (`agents/Agent_C`)

Zéro appel LLM : ne connaît que la forme de `AlignmentEdge`/`Node`.

- `nodes.prepare_report_data(...) -> ReportData` — sépare la préparation des
  données (tri par sévérité, regroupement des "inchangés", gestion des
  trous) du rendu.
- `nodes.make_composite_image(...)` — image unique "entrée | sortie" par
  checkpoint en écart (PIL), plus robuste que deux images flottantes.
- `graph.render_pdf(report_data, output_path)` — rendu reportlab pur,
  testable avec des données mockées (`python -m agents.Agent_C.graph`).
- `graph.build_report(...)` — pipeline complet `prepare_report_data` ->
  composites -> `render_pdf`.

## Installation (uv, Python 3.12)

```bash
uv venv --python 3.12          # crée .venv/ en Python 3.12
uv sync                         # installe les dépendances depuis pyproject.toml (+ uv.lock)
```

`requirements.txt` est régénéré depuis le lock (`uv export --no-hashes -o requirements.txt`)
et fourni uniquement pour compatibilité `pip`, ce n'est pas la source de vérité.

Deux options pour la clé API (équivalentes, `load_dotenv()` ne remplace jamais
une variable déjà présente dans l'environnement) :

```bash
# Option 1 — export dans le terminal (valable pour la session en cours)
export NVIDIA_API_KEY="votre_clé"

# Option 2 — fichier .env à la racine (persistant, voir .env.example)
cp .env.example .env   # puis éditer .env avec la vraie clé
```

## Triggers indépendants (un par module)

Chaque module a son propre point d'entrée dans `scripts/`, à lancer
individuellement — il n'y a pas de run automatique qui enchaîne les 4
modules. Tous fonctionnent en mode "smoke test" sans données réelles quand
c'est possible (A avec `--images-dir` absent, C avec `--mock`, D en Mode 1
avec la démo intégrée) ; B nécessite toujours `NVIDIA_API_KEY` (compare_node
appelle systématiquement le VLM).

```bash
# Module A — construction du graphe (smoke test si pas d'images fournies)
uv run scripts/run_agent_a.py --config config/checkpoints.example.json \
    --images-dir data/appt-12/entry --output entry_graph.json

# Module B — alignement entrée/sortie (nécessite NVIDIA_API_KEY)
uv run scripts/run_agent_b.py --entry-graph entry_graph.json \
    --exit-graph exit_graph.json --output edges.json

# Module D — qualification légale (Mode 1 déterministe par défaut, sans clé API)
uv run scripts/run_agent_d.py --edge edge.json --occupancy-months 36 \
    --element-category mur --grid config/vetuste_grid.example.json

# Module C — génération du PDF (zéro LLM, --mock pour tester sans rien d'autre)
uv run scripts/run_agent_c.py --mock --output rapport_mock.pdf
```

Voir l'en-tête de chaque script pour le détail des options.

## Test visuel (Module A + B + watermark de divergence)

`AlignmentEdge` porte un champ `bbox_pct` : la zone de divergence localisée
par le VLM, en coordonnées normalisées `[x_min, y_min, x_max, y_max]`
(0 à 1). `agents/Agent_B/visualize.annotate_divergence` s'en sert pour
superposer un watermark très transparent — **vert** sur l'image d'entrée,
**rouge** sur l'image de sortie — à l'endroit exact du problème détecté.

```bash
# 1. Déposer deux photos du même checkpoint (voir data/test/README.md)
cp votre_photo_avant.jpg data/test/entry.jpg
cp votre_photo_apres.jpg data/test/exit.jpg

# 2. Lancer le test (nécessite NVIDIA_API_KEY)
uv run scripts/run_visual_test.py

# 3. Résultat dans data/test/annotated/ : {checkpoint}_avant.jpg / {checkpoint}_apres.jpg
```

Si le VLM ne peut pas localiser précisément l'anomalie (`bbox_pct=null`,
p. ex. `status="unchanged"` ou changement diffus), un simple liseré coloré
encadre l'image entière plutôt qu'une zone remplie.

La position du cercle n'est pas prise telle quelle depuis `bbox_pct` (les
VLM généralistes localisent grossièrement) : `annotate_divergence` calcule
un centroïde par **différence d'image classique** entre les deux photos
(zéro LLM, déterministe), en isolant le plus gros blob de pixels divergents
par composantes connexes — ce qui écarte le bruit ambiant (reflets,
luminosité changeante) qui, lui, se fragmente en petites taches éparses.

## Pipeline complet véhicule (multi-entités, Module A -> B -> D -> C)

Domaine où une photo montre **plusieurs checkpoints à la fois** (ex :
extérieur de véhicule = pare-choc + portière + aile + jante + pare-brise
sur une seule image). 4 photos au total : extérieur/intérieur x avant/après.

```bash
# 1. Déposer vos 4 photos (voir data/test/vehicule/README.md)
cp entree_ext.jpg data/test/vehicule/entry_exterieur.jpg
cp entree_int.jpg data/test/vehicule/entry_interieur.jpg
cp sortie_ext.jpg data/test/vehicule/exit_exterieur.jpg
cp sortie_int.jpg data/test/vehicule/exit_interieur.jpg

# 2. Lancer le pipeline complet (nécessite NVIDIA_API_KEY)
uv run scripts/run_pipeline_vehicule.py
```

Résultat : `data/test/vehicule/rapport_vehicule.pdf` (Module C) +
`data/test/vehicule/annotated/` (une paire d'images annotées par écart
détecté, localisation prioritairement basée sur le `bbox_pct` du Module A
pour ne pas confondre deux checkpoints voisins visibles sur la même photo).

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
  common/schemas.py        # contrat de données partagé entre A, B, C, D
  base_model/base_llm_nim.py  # provider LLM (NVIDIA API), support texte + images
  Agent_A/  (state.py, prompts/, nodes/, graph.py)  # Module A
  Agent_B/  (state.py, prompts/, nodes/, graph.py)  # Module B
  Agent_C/  (state.py, prompts/, nodes/, graph.py)  # Module C
  Agent_D/  (state.py, prompts/, nodes/, graph.py)  # Module D
config/
  checkpoints.example.json           # squelette checkpoints, mode "1 image = 1 checkpoint"
  checkpoints_vehicule.example.json  # squelette checkpoints, mode multi-entités (véhicule)
  vetuste_grid.example.json          # grille de vétusté contractuelle (Module D, Mode 1)
scripts/
  run_agent_a.py / run_agent_b.py / run_agent_c.py / run_agent_d.py  # triggers indépendants
  run_visual_test.py          # test A+B avec watermark de divergence (vert/rouge)
  run_pipeline_vehicule.py    # pipeline complet A -> B -> D -> C, domaine véhicule (multi-entités)
data/test/
  entry.jpg / exit.jpg        # vos deux photos à comparer (non trackées, voir data/test/README.md)
  annotated/                   # images annotées générées par run_visual_test.py
  vehicule/                    # 4 photos + rapport pour le pipeline véhicule (voir vehicule/README.md)
pyproject.toml / uv.lock       # gestion des dépendances (uv, Python 3.12)
```

## Avertissement légal

Le Module D produit une **analyse indicative** : il ne remplace pas une
expertise contradictoire ou un avis juridique. En l'absence de grille de
vétusté annexée au bail, la qualification s'appuie sur un raisonnement par
analogie avec des critères jurisprudentiels usuels, pas sur un texte de loi
qui trancherait le cas de manière automatique.
