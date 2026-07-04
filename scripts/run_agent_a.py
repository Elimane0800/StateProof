#!/usr/bin/env python3
"""
Trigger indépendant — Module A (construction du graphe LPG).

Usage :
    uv run scripts/run_agent_a.py
    uv run scripts/run_agent_a.py --config config/checkpoints.example.json \\
        --images-dir data/appt-12/entry --output entry_graph.json

Sans --images-dir ni --images-map, le script tourne quand même (smoke test) :
il produit un graphe vide, ce qui valide le câblage (config, imports,
LangGraph) sans clé API ni images réelles.

Convention de nommage des images dans --images-dir :
    {room}__{checkpoint_id}.<ext>   ex: salon__mur_nord.jpg
Alternative : --images-map, un JSON {"room:checkpoint_id": "chemin"}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.Agent_A.graph import build_graph  # noqa: E402
from agents.common.schemas import PropertyConfig  # noqa: E402


def discover_images(images_dir: Path) -> dict:
    images: dict = {}
    if not images_dir.exists():
        return images
    for f in sorted(images_dir.iterdir()):
        if f.is_file() and "__" in f.stem:
            room, checkpoint_id = f.stem.split("__", 1)
            images[f"{room}:{checkpoint_id}"] = str(f)
    return images


def main() -> None:
    parser = argparse.ArgumentParser(description="Module A — build_graph (entry_graph ou exit_graph)")
    parser.add_argument("--config", default="config/checkpoints.example.json")
    parser.add_argument("--images-dir", default=None)
    parser.add_argument("--images-map", default=None, help="JSON {'room:checkpoint_id': 'chemin'} (prioritaire sur --images-dir)")
    parser.add_argument("--output", default="graph.json")
    args = parser.parse_args()

    config = PropertyConfig.from_json_file(args.config)

    if args.images_map:
        images_by_checkpoint = json.loads(Path(args.images_map).read_text())
    elif args.images_dir:
        images_by_checkpoint = discover_images(Path(args.images_dir))
    else:
        images_by_checkpoint = {}
        print("[Module A] Aucune image fournie (--images-dir/--images-map) : "
              "smoke test de câblage, le graphe produit sera vide, zéro appel LLM.")

    try:
        graph = build_graph(config, images_by_checkpoint)
    except Exception as e:  # noqa: BLE001 — trigger CLI : on veut un message clair, pas une trace brute
        print(f"[Module A] Échec : {e}\n"
              "Vérifiez NVIDIA_API_KEY (export dans le terminal ou fichier .env) si des images étaient fournies.")
        sys.exit(1)

    Path(args.output).write_text(graph.model_dump_json(indent=2, ensure_ascii=False))
    print(f"[Module A] {len(graph.nodes)} nœud(s) construit(s) -> {args.output}")


if __name__ == "__main__":
    main()
