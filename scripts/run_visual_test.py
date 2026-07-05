#!/usr/bin/env python3
"""
Visual test trigger — Module A (x2) + Module B + divergence watermark.

Takes two photos of the same checkpoint (before/after), rebuilds both `Node`s
(Module A), compares them (Module B), then writes two annotated images with a
very transparent watermark on the detected divergence zone: GREEN on the entry
image, RED on the exit image.

Usage:
    uv run scripts/run_visual_test.py
    uv run scripts/run_visual_test.py \\
        --entry-image data/test/entry.jpg --exit-image data/test/exit.jpg \\
        --checkpoint-id mur_nord --room salon --element-type mur \\
        --output-dir data/test/annotated

Requires NVIDIA_API_KEY (Module A + B both make VLM calls).
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
    parser = argparse.ArgumentParser(description="Visual test Module A + B — divergence watermark")
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
        print(f"[Visual test] Images not found: {entry_image} / {exit_image}\n"
              "Drop your two photos in data/test/ (see data/test/README.md).")
        sys.exit(1)

    try:
        print("[Visual test] Module A — state description (entry)...")
        entry_node = build_node(str(entry_image), args.checkpoint_id, args.room, args.element_type)
        print("[Visual test] Module A — state description (exit)...")
        exit_node = build_node(str(exit_image), args.checkpoint_id, args.room, args.element_type)

        print("[Visual test] Module B — entry/exit comparison...")
        edge = compare_node(entry_node, exit_node)
    except Exception as e:  # noqa: BLE001
        print(f"[Visual test] Failed: {e}\nCheck NVIDIA_API_KEY (export in terminal or .env file).")
        sys.exit(1)

    print(json.dumps(edge.model_dump(), indent=2, ensure_ascii=False))

    entry_out, exit_out = annotate_divergence(str(entry_image), str(exit_image), edge, args.output_dir)
    print(f"[Visual test] Annotated images -> {entry_out} (green) / {exit_out} (red)")


if __name__ == "__main__":
    main()
