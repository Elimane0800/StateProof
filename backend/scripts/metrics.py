"""Measure REAL Taste Engine accuracy over the 6 golden cases.

These are the only numbers used in the pitch. Run with keys set to measure the
real VLM, or without keys to measure the deterministic heuristic.

    python backend/scripts/metrics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.schema import AuditRequest  # noqa: E402
from app.services import classifier, tree_builder, vlm  # noqa: E402
from tests.golden_cases import CASES  # noqa: E402


def signals(payload) -> dict:
    return {
        "violation": len(payload.findings) > 0,
        "noise": len(payload.ignored_as_noise) > 0,
        "evolution": len(payload.evolution_proposals) > 0,
    }


def main() -> int:
    mode = "REAL VLM" if vlm.available() else "heuristic (no VLM keys)"
    print(f"SynchronAIse metrics - engine: {mode}\n")

    correct = 0
    noise_ok = 0
    noise_total = 0
    print(f"{'PR':<4}{'case':<48}{'expected':<28}{'predicted':<28}{'ok'}")
    for case in CASES:
        req = AuditRequest(pr_number=case.pr_number, code=case.code, file_path="StatusCard.tsx")
        design, codetree = tree_builder.build_trees(req)
        payload = classifier.classify(req, design, codetree)
        pred = signals(payload)
        exp = case.expected

        if case.vlm_only and not vlm.available():
            ok = None  # not scored on the heuristic
        else:
            ok = all(pred[k] == exp[k] for k in exp)
            correct += 1 if ok else 0

        if exp.get("noise"):
            noise_total += 1
            if pred["noise"]:
                noise_ok += 1

        exp_s = ",".join(k for k, v in exp.items() if v) or "aligned"
        pred_s = ",".join(k for k, v in pred.items() if v) or "aligned"
        mark = "-" if ok is None else ("PASS" if ok else "FAIL")
        print(f"{case.pr_number:<4}{case.title[:46]:<48}{exp_s:<28}{pred_s:<28}{mark}")

    scored = sum(1 for c in CASES if not (c.vlm_only and not vlm.available()))
    print(f"\nClassification: {correct}/{scored} correct")
    print(f"Noise correctly ignored: {noise_ok}/{noise_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
