"""Accuracy of the Taste Engine over the 6 golden cases (heuristic path).

These lock in the deterministic behavior so the pipeline is always green in CI.
The real-VLM path is exercised manually with API keys.
"""

from __future__ import annotations

import pytest

from app.core.schema import AuditPayload, AuditRequest, Classification
from app.services import classifier, tree_builder
from tests.golden_cases import CASES


def _run(code: str, pr_number: int) -> AuditPayload:
    req = AuditRequest(pr_number=pr_number, code=code, file_path="StatusCard.tsx")
    design, codetree = tree_builder.build_trees(req)
    return classifier.classify(req, design, codetree)


@pytest.mark.parametrize("case", CASES, ids=[c.title for c in CASES])
def test_signal_separation(case) -> None:
    payload = _run(case.code, case.pr_number)

    if case.vlm_only:
        # Structural reasoning needs the VLM; here we only assert a valid payload.
        assert isinstance(payload, AuditPayload)
        return

    has_violation = len(payload.findings) > 0
    has_noise = len(payload.ignored_as_noise) > 0
    has_evolution = len(payload.evolution_proposals) > 0

    assert has_violation == case.expected["violation"], f"violation flag wrong for PR#{case.pr_number}"
    assert has_noise == case.expected["noise"], f"noise flag wrong for PR#{case.pr_number}"
    assert has_evolution == case.expected["evolution"], f"evolution flag wrong for PR#{case.pr_number}"


def test_case_1_token_violation_details() -> None:
    payload = _run(CASES[0].code, 1)
    finding = next(f for f in payload.findings if f.node_id == "btn-primary")
    assert finding.classification == Classification.DESIGN_VIOLATION
    assert finding.expected == "var(--color-danger)"
    assert finding.actual == "#ef4444"
    assert "color-danger" in finding.reasoning


def test_case_3_wrapper_is_noise_not_violation() -> None:
    payload = _run(CASES[2].code, 3)
    assert payload.findings == []
    assert any("wrapper" in n.element or "scroll" in n.element for n in payload.ignored_as_noise)
