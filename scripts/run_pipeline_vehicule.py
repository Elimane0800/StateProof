#!/usr/bin/env python3
"""
Trigger — full vehicle pipeline: Module A -> B -> D -> C.

"Vehicle" domain: unlike real estate (1 photo = 1 checkpoint), ONE photo here
contains SEVERAL checkpoints at once (e.g. an exterior photo shows bumper +
door + wheel + windshield together). The pipeline therefore expects 4 photos
total: exterior/interior × before/after.

Steps:
  1. Module A (build_graph_from_zone_images) — 1 VLM call per photo (2 per state:
     exterior + interior), each call extracts ALL visible checkpoints + their
     localization (bbox_pct) in that photo.
  2. Module B (align) — compares each common entry/exit checkpoint, produces
     `AlignmentEdge`s (status, severity, cost, bbox_pct).
  3. Visualization (annotate_divergence) — localized circle on each divergence,
     preferring Module A localization (essential when several checkpoints share
     the same photo).
  4. Module D (qualify) — legal qualification of each divergence (wear vs
     damage), Mode 1 (grid) if `--grid` covers the category, else Mode 2 (LLM).
  5. Module C (build_report) — assembles everything into a final PDF.

Usage:
    uv run scripts/run_pipeline_vehicule.py

    uv run scripts/run_pipeline_vehicule.py \\
        --config config/checkpoints_vehicule.example.json \\
        --entry-exterior data/test/vehicule/entry_exterieur.jpg \\
        --entry-interior data/test/vehicule/entry_interieur.jpg \\
        --exit-exterior data/test/vehicule/exit_exterieur.jpg \\
        --exit-interior data/test/vehicule/exit_interieur.jpg \\
        --occupancy-months 12 \\
        --output-pdf data/test/vehicule/rapport_vehicule.pdf

Requires NVIDIA_API_KEY (Modules A, B, and D Mode 2 make LLM/VLM calls).
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
    parser = argparse.ArgumentParser(description="Full vehicle pipeline — Module A -> B -> D -> C")
    parser.add_argument("--config", default="config/checkpoints_vehicule.example.json")
    parser.add_argument("--entry-exterior", default="data/test/vehicule/entry_exterieur.jpg")
    parser.add_argument("--entry-interior", default="data/test/vehicule/entry_interieur.jpg")
    parser.add_argument("--exit-exterior", default="data/test/vehicule/exit_exterieur.jpg")
    parser.add_argument("--exit-interior", default="data/test/vehicule/exit_interieur.jpg")
    parser.add_argument("--occupancy-months", type=int, default=12,
                         help="Duration between entry and exit (months), used by Module D.")
    parser.add_argument("--grid", default=None,
                         help="Wear grid JSON (Module D Mode 1). Optional.")
    parser.add_argument("--address", default=None)
    parser.add_argument("--output-pdf", default="data/test/vehicule/rapport_vehicule.pdf")
    parser.add_argument("--annotated-dir", default="data/test/vehicule/annotated")
    parser.add_argument("--composites-dir", default="data/test/vehicule/composites")
    args = parser.parse_args()

    images = {
        "entry / exterior": Path(args.entry_exterior),
        "entry / interior": Path(args.entry_interior),
        "exit / exterior": Path(args.exit_exterior),
        "exit / interior": Path(args.exit_interior),
    }
    missing = [label for label, path in images.items() if not path.exists()]
    if missing:
        print("[Vehicle pipeline] Missing photo(s): " + ", ".join(missing))
        print("Drop your 4 photos in data/test/vehicule/ (see data/test/vehicule/README.md).")
        sys.exit(1)

    config = PropertyConfig.from_json_file(args.config)

    try:
        print("[Module A] Entry extraction (exterior + interior)...")
        entry_graph = build_graph_from_zone_images(config, {
            "exterieur": str(images["entry / exterior"]),
            "interieur": str(images["entry / interior"]),
        })
        print(f"[Module A] {len(entry_graph.nodes)} checkpoint(s) extracted at entry.")

        print("[Module A] Exit extraction (exterior + interior)...")
        exit_graph = build_graph_from_zone_images(config, {
            "exterieur": str(images["exit / exterior"]),
            "interieur": str(images["exit / interior"]),
        })
        print(f"[Module A] {len(exit_graph.nodes)} checkpoint(s) extracted at exit.")

        print("[Module B] Entry/exit comparison...")
        edges = align(entry_graph, exit_graph)
        score = compute_confidence_score(edges)
        print(f"[Module B] {len(edges)} checkpoint(s) compared — global confidence score: {score:.2f}")

        grid = _load_grid(args.grid)
        legal_qualifications: Dict[str, LegalQualification] = {}

        print("[Visualization + Module D] Processing detected divergences...")
        Path(args.annotated_dir).mkdir(parents=True, exist_ok=True)
        for edge in edges:
            status = edge.status.value if hasattr(edge.status, "value") else str(edge.status)
            if status == "unchanged":
                continue

            entry_node = entry_graph.get_node(edge.node_id)
            exit_node = exit_graph.get_node(edge.node_id)
            print(f"  - {edge.node_id}: {status} (severity={edge.severity}, cost~{edge.estimated_cost_eur:.0f}€)")
            print(f"    {edge.reasoning}")

            if entry_node and exit_node and entry_node.image_path and exit_node.image_path:
                try:
                    annotate_divergence(
                        entry_node.image_path, exit_node.image_path, edge, args.annotated_dir,
                        entry_node=entry_node, exit_node=exit_node,
                    )
                except (FileNotFoundError, OSError) as e:
                    print(f"    (visual annotation failed: {e})")

            legal_qualifications[edge.node_id] = qualify(
                edge, args.occupancy_months,
                element_category=(entry_node or exit_node).element_type if (entry_node or exit_node) else None,
                grid=grid, entry_node=entry_node, exit_node=exit_node,
            )

        print("[Module C] Generating PDF report...")
        output_path = build_report(
            entry_graph, exit_graph, edges, score, args.output_pdf,
            legal_qualifications=legal_qualifications,
            address=args.address,
            composites_dir=args.composites_dir,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[Vehicle pipeline] Failed: {e}\nCheck NVIDIA_API_KEY (export in terminal or .env file).")
        sys.exit(1)

    print(f"\n[Vehicle pipeline] Report generated -> {output_path}")
    print(f"[Vehicle pipeline] Annotated images -> {args.annotated_dir}/")


if __name__ == "__main__":
    main()
