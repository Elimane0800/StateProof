#!/usr/bin/env python3
"""
Trigger — pipeline complet véhicule : Module A -> B -> D -> C.

Domaine "véhicule" : contrairement au domaine immobilier (1 photo = 1
checkpoint), ici UNE photo contient PLUSIEURS checkpoints à la fois (ex :
une photo d'extérieur montre pare-choc + portière + jante + pare-brise en
même temps). Le pipeline attend donc 4 photos au total : extérieur/intérieur
x avant/après.

Étapes :
  1. Module A (build_graph_from_zone_images) — 1 appel VLM par photo (donc 2
     par état : extérieur + intérieur), chaque appel extrait TOUS les
     checkpoints visibles + leur localisation (bbox_pct) dans cette photo.
  2. Module B (align) — compare chaque checkpoint commun entrée/sortie,
     produit les `AlignmentEdge` (status, sévérité, coût, bbox_pct).
  3. Visualisation (annotate_divergence) — cercle localisé sur chaque écart,
     en utilisant en priorité la localisation du Module A (indispensable
     puisque plusieurs checkpoints partagent la même photo).
  4. Module D (qualify) — qualification légale de chaque écart (vétusté vs
     dégradation), Mode 1 (grille) si `--grid` couvre la catégorie, sinon
     Mode 2 (raisonnement LLM).
  5. Module C (build_report) — assemble tout dans un PDF final.

Usage :
    uv run scripts/run_pipeline_vehicule.py

    uv run scripts/run_pipeline_vehicule.py \\
        --config config/checkpoints_vehicule.example.json \\
        --entry-exterior data/test/vehicule/entry_exterieur.jpg \\
        --entry-interior data/test/vehicule/entry_interieur.jpg \\
        --exit-exterior data/test/vehicule/exit_exterieur.jpg \\
        --exit-interior data/test/vehicule/exit_interieur.jpg \\
        --occupancy-months 12 \\
        --output-pdf data/test/vehicule/rapport_vehicule.pdf

Nécessite NVIDIA_API_KEY (Modules A, B et D-Mode2 font des appels LLM/VLM).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.Agent_A.graph import build_graph_from_zone_images  # noqa: E402
from agents.Agent_B.graph import align, compute_confidence_score  # noqa: E402
from agents.Agent_B.visualize import annotate_divergence  # noqa: E402
from agents.Agent_C.graph import build_report  # noqa: E402
from agents.Agent_D.graph import qualify  # noqa: E402
from agents.common.schemas import LegalQualification, PropertyConfig, VetusteGridEntry  # noqa: E402


def _load_grid(path: Optional[str]) -> Optional[Dict[str, VetusteGridEntry]]:
    if not path or not Path(path).exists():
        return None
    raw_grid = json.loads(Path(path).read_text())
    return {k: VetusteGridEntry.model_validate(v) for k, v in raw_grid.items() if not k.startswith("_")}


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline complet véhicule — Module A -> B -> D -> C")
    parser.add_argument("--config", default="config/checkpoints_vehicule.example.json")
    parser.add_argument("--entry-exterior", default="data/test/vehicule/entry_exterieur.jpg")
    parser.add_argument("--entry-interior", default="data/test/vehicule/entry_interieur.jpg")
    parser.add_argument("--exit-exterior", default="data/test/vehicule/exit_exterieur.jpg")
    parser.add_argument("--exit-interior", default="data/test/vehicule/exit_interieur.jpg")
    parser.add_argument("--occupancy-months", type=int, default=12,
                         help="Durée entre l'état d'entrée et de sortie (mois), utilisée par le Module D.")
    parser.add_argument("--grid", default=None,
                         help="JSON de grille de vétusté (Mode 1 du Module D). Optionnel.")
    parser.add_argument("--address", default=None)
    parser.add_argument("--output-pdf", default="data/test/vehicule/rapport_vehicule.pdf")
    parser.add_argument("--annotated-dir", default="data/test/vehicule/annotated")
    parser.add_argument("--composites-dir", default="data/test/vehicule/composites")
    args = parser.parse_args()

    images = {
        "entrée / extérieur": Path(args.entry_exterior),
        "entrée / intérieur": Path(args.entry_interior),
        "sortie / extérieur": Path(args.exit_exterior),
        "sortie / intérieur": Path(args.exit_interior),
    }
    missing = [label for label, path in images.items() if not path.exists()]
    if missing:
        print("[Pipeline véhicule] Photo(s) manquante(s) : " + ", ".join(missing))
        print("Déposez vos 4 photos dans data/test/vehicule/ (voir data/test/vehicule/README.md).")
        sys.exit(1)

    config = PropertyConfig.from_json_file(args.config)

    try:
        print("[Module A] Extraction entrée (extérieur + intérieur)...")
        entry_graph = build_graph_from_zone_images(config, {
            "exterieur": str(images["entrée / extérieur"]),
            "interieur": str(images["entrée / intérieur"]),
        })
        print(f"[Module A] {len(entry_graph.nodes)} checkpoint(s) extrait(s) à l'entrée.")

        print("[Module A] Extraction sortie (extérieur + intérieur)...")
        exit_graph = build_graph_from_zone_images(config, {
            "exterieur": str(images["sortie / extérieur"]),
            "interieur": str(images["sortie / intérieur"]),
        })
        print(f"[Module A] {len(exit_graph.nodes)} checkpoint(s) extrait(s) à la sortie.")

        print("[Module B] Comparaison entrée/sortie...")
        edges = align(entry_graph, exit_graph)
        score = compute_confidence_score(edges)
        print(f"[Module B] {len(edges)} checkpoint(s) comparé(s) — score de confiance global : {score:.2f}")

        grid = _load_grid(args.grid)
        legal_qualifications: Dict[str, LegalQualification] = {}

        print("[Visualisation + Module D] Traitement des écarts détectés...")
        Path(args.annotated_dir).mkdir(parents=True, exist_ok=True)
        for edge in edges:
            status = edge.status.value if hasattr(edge.status, "value") else str(edge.status)
            if status == "unchanged":
                continue

            entry_node = entry_graph.get_node(edge.node_id)
            exit_node = exit_graph.get_node(edge.node_id)
            print(f"  - {edge.node_id} : {status} (sévérité={edge.severity}, coût~{edge.estimated_cost_eur:.0f}€)")
            print(f"    {edge.reasoning}")

            if entry_node and exit_node and entry_node.image_path and exit_node.image_path:
                try:
                    annotate_divergence(
                        entry_node.image_path, exit_node.image_path, edge, args.annotated_dir,
                        entry_node=entry_node, exit_node=exit_node,
                    )
                except (FileNotFoundError, OSError) as e:
                    print(f"    (annotation visuelle impossible : {e})")

            legal_qualifications[edge.node_id] = qualify(
                edge, args.occupancy_months,
                element_category=(entry_node or exit_node).element_type if (entry_node or exit_node) else None,
                grid=grid, entry_node=entry_node, exit_node=exit_node,
            )

        print("[Module C] Génération du rapport PDF...")
        output_path = build_report(
            entry_graph, exit_graph, edges, score, args.output_pdf,
            legal_qualifications=legal_qualifications,
            address=args.address,
            composites_dir=args.composites_dir,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[Pipeline véhicule] Échec : {e}\nVérifiez NVIDIA_API_KEY (export dans le terminal ou fichier .env).")
        sys.exit(1)

    print(f"\n[Pipeline véhicule] Rapport généré -> {output_path}")
    print(f"[Pipeline véhicule] Images annotées -> {args.annotated_dir}/")


if __name__ == "__main__":
    main()
