#!/usr/bin/env python3
"""
Trigger de test visuel — Module A (x2) + Module B + watermark de divergence.

Prend deux photos d'un même checkpoint (avant/après), reconstruit les deux
`Node` (Module A), les compare (Module B), puis écrit deux images annotées
avec un watermark très transparent sur la zone de divergence détectée par
le VLM : VERT sur l'image d'entrée, ROUGE sur l'image de sortie.

Usage :
    uv run scripts/run_visual_test.py
    uv run scripts/run_visual_test.py \\
        --entry-image data/test/entry.jpg --exit-image data/test/exit.jpg \\
        --checkpoint-id mur_nord --room salon --element-type mur \\
        --output-dir data/test/annotated

Nécessite NVIDIA_API_KEY (Module A + B font tous les deux un appel VLM).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.Agent_A.nodes import build_node  # noqa: E402
from agents.Agent_B.nodes import compare_node  # noqa: E402
from agents.Agent_B.visualize import annotate_divergence  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Test visuel Module A + B — watermark de divergence")
    parser.add_argument("--entry-image", default="data/test/entry.jpg")
    parser.add_argument("--exit-image", default="data/test/exit.jpg")
    parser.add_argument("--checkpoint-id", default="test")
    parser.add_argument("--room", default="piece_test")
    parser.add_argument("--element-type", default=None)
    parser.add_argument("--output-dir", default="data/test/annotated")
    args = parser.parse_args()

    entry_image = Path(args.entry_image)
    exit_image = Path(args.exit_image)
    if not entry_image.exists() or not exit_image.exists():
        print(f"[Test visuel] Images introuvables : {entry_image} / {exit_image}\n"
              "Déposez vos deux photos dans data/test/ (voir data/test/README.md).")
        sys.exit(1)

    try:
        print("[Test visuel] Module A — description de l'état (entrée)...")
        entry_node = build_node(str(entry_image), args.checkpoint_id, args.room, args.element_type)
        print("[Test visuel] Module A — description de l'état (sortie)...")
        exit_node = build_node(str(exit_image), args.checkpoint_id, args.room, args.element_type)

        print("[Test visuel] Module B — comparaison entrée/sortie...")
        edge = compare_node(entry_node, exit_node)
    except Exception as e:  # noqa: BLE001
        print(f"[Test visuel] Échec : {e}\nVérifiez NVIDIA_API_KEY (export dans le terminal ou fichier .env).")
        sys.exit(1)

    print(json.dumps(edge.model_dump(), indent=2, ensure_ascii=False))

    entry_out, exit_out = annotate_divergence(str(entry_image), str(exit_image), edge, args.output_dir)
    print(f"[Test visuel] Images annotées -> {entry_out} (vert) / {exit_out} (rouge)")


if __name__ == "__main__":
    main()
