#!/usr/bin/env python3
"""
Independent trigger — Module A (LPG graph construction).

Usage:
    uv run scripts/run_agent_a.py
    uv run scripts/run_agent_a.py --config config/checkpoints.example.json \\
        --images-dir data/appt-12/entry --output entry_graph.json

Without --images-dir or --images-map, the script still runs (smoke test): it
produces an empty graph, validating wiring (config, imports, LangGraph) without
an API key or real images.

Image naming convention in --images-dir:
    {room}__{checkpoint_id}.<ext>   e.g. salon__mur_nord.jpg
Alternative: --images-map, a JSON {"room:checkpoint_id": "path"}.
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
    parser = argparse.ArgumentParser(description="Module A — build_graph (entry_graph or exit_graph)")
    parser.add_argument("--config", default="config/checkpoints.example.json")
    parser.add_argument("--images-dir", default=None)
    parser.add_argument("--images-map", default=None, help="JSON {'room:checkpoint_id': 'path'} (overrides --images-dir)")
    parser.add_argument("--output", default="graph.json")
    args = parser.parse_args()

    config = PropertyConfig.from_json_file(args.config)

    if args.images_map:
        images_by_checkpoint = json.loads(Path(args.images_map).read_text())
    elif args.images_dir:
        images_by_checkpoint = discover_images(Path(args.images_dir))
    else:
        images_by_checkpoint = {}
        print("[Module A] No images provided (--images-dir/--images-map): "
              "wiring smoke test; output graph will be empty, zero LLM calls.")

    try:
        graph = build_graph(config, images_by_checkpoint)
    except Exception as e:  # noqa: BLE001 — CLI trigger: clear message, not a raw traceback
        print(f"[Module A] Failed: {e}\n"
              "Check NVIDIA_API_KEY (export in terminal or .env file) if images were provided.")
        sys.exit(1)

    Path(args.output).write_text(graph.model_dump_json(indent=2, ensure_ascii=False))
    print(f"[Module A] {len(graph.nodes)} node(s) built -> {args.output}")


if __name__ == "__main__":
    main()
