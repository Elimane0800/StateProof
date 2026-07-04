#!/usr/bin/env python3
"""
Trigger indépendant — Module B (détection / alignement entrée-sortie).

Usage :
    uv run scripts/run_agent_b.py
    uv run scripts/run_agent_b.py --entry-graph entry_graph.json \\
        --exit-graph exit_graph.json --output edges.json

Sans --entry-graph/--exit-graph, tourne sur une paire de Node mockés (aucune
dépendance sur le Module A) — nécessite quand même NVIDIA_API_KEY, car
compare_node fait toujours un appel LLM (pas de mode "zéro LLM" côté B).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.Agent_B.graph import align, compute_confidence_score  # noqa: E402
from agents.common.schemas import Graph, Node, NodeProperties  # noqa: E402


def _mock_graphs():
    entry = Graph(property_id="demo", nodes={
        "salon:mur_nord": Node(
            id="salon:mur_nord", checkpoint_id="mur_nord", room="salon", element_type="mur",
            properties=NodeProperties(material="plâtre peint", color="blanc", condition="intact", confidence=0.94),
        )
    })
    exit_ = Graph(property_id="demo", nodes={
        "salon:mur_nord": Node(
            id="salon:mur_nord", checkpoint_id="mur_nord", room="salon", element_type="mur",
            properties=NodeProperties(material="plâtre peint", color="blanc", condition="endommagé",
                                       defects=["trou"], confidence=0.9),
        )
    })
    return entry, exit_


def main() -> None:
    parser = argparse.ArgumentParser(description="Module B — align + compute_confidence_score")
    parser.add_argument("--entry-graph", default=None)
    parser.add_argument("--exit-graph", default=None)
    parser.add_argument("--output", default="edges.json")
    args = parser.parse_args()

    if args.entry_graph and args.exit_graph:
        entry_graph = Graph.model_validate_json(Path(args.entry_graph).read_text())
        exit_graph = Graph.model_validate_json(Path(args.exit_graph).read_text())
    else:
        print("[Module B] Aucun graphe fourni (--entry-graph/--exit-graph) : "
              "smoke test sur une paire de Node mockés (appel LLM réel malgré tout).")
        entry_graph, exit_graph = _mock_graphs()

    try:
        edges = align(entry_graph, exit_graph)
    except Exception as e:  # noqa: BLE001
        print(f"[Module B] Échec : {e}\nVérifiez NVIDIA_API_KEY (export dans le terminal ou fichier .env).")
        sys.exit(1)

    score = compute_confidence_score(edges)

    Path(args.output).write_text(json.dumps([e.model_dump() for e in edges], indent=2, ensure_ascii=False))
    print(f"[Module B] {len(edges)} arête(s) -> {args.output} | confidence_score = {score}")


if __name__ == "__main__":
    main()
