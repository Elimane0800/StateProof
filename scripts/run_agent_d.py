#!/usr/bin/env python3
"""
Independent trigger — Module D (legal qualification).

Usage:
    # Mode 1 (deterministic), built-in demo, no API key required:
    uv run scripts/run_agent_d.py

    # Mode 1 with a real grid and edge:
    uv run scripts/run_agent_d.py --edge edge.json --occupancy-months 36 \\
        --element-category mur --grid config/vetuste_grid.example.json

    # Mode 2 (LLM reasoning by case-law analogy, requires NVIDIA_API_KEY):
    uv run scripts/run_agent_d.py --edge edge.json --occupancy-months 8 --force-mode2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.Agent_D.graph import qualify  # noqa: E402
from agents.Agent_D.nodes import qualify_with_llm  # noqa: E402
from agents.common.schemas import AlignmentEdge, VetusteGridEntry  # noqa: E402


def _demo_edge() -> AlignmentEdge:
    return AlignmentEdge(
        node_id="salon:mur_nord", checkpoint_id="mur_nord", room="salon",
        status="damage", severity="high", confidence=0.91,
        reasoning="Localized impact incompatible with normal aging.",
        estimated_cost_eur=45,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Module D — qualify (Mode 1 deterministic / Mode 2 LLM)")
    parser.add_argument("--edge", default=None, help="JSON AlignmentEdge")
    parser.add_argument("--occupancy-months", type=int, default=36)
    parser.add_argument("--element-category", default="mur")
    parser.add_argument("--grid", default="config/vetuste_grid.example.json")
    parser.add_argument("--force-mode2", action="store_true",
                         help="Force LLM reasoning even if a grid covers the category.")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.edge:
        edge = AlignmentEdge.model_validate_json(Path(args.edge).read_text())
    else:
        print("[Module D] No --edge provided: built-in demo (Mode 1, no API key).")
        edge = _demo_edge()

    try:
        if args.force_mode2:
            result = qualify_with_llm(edge, args.occupancy_months)
        else:
            grid = None
            if args.grid and Path(args.grid).exists():
                raw_grid = json.loads(Path(args.grid).read_text())
                grid = {k: VetusteGridEntry.model_validate(v) for k, v in raw_grid.items() if not k.startswith("_")}
            result = qualify(edge, args.occupancy_months, element_category=args.element_category, grid=grid)
    except Exception as e:  # noqa: BLE001
        print(f"[Module D] Failed: {e}\nCheck NVIDIA_API_KEY (export in terminal or .env file) if Mode 2 was requested.")
        sys.exit(1)

    output_json = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output_json)
        print(f"[Module D] Qualification -> {args.output}")
    else:
        print(f"[Module D] {output_json}")


if __name__ == "__main__":
    main()
