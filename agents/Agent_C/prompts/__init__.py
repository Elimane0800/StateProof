"""
Agent C — No LLM prompts here (zero LLM calls in all of Module C).

This file exists for structural consistency with other agents and holds static
report text (labels, methodology, disclaimer) so it is not scattered in render code.
"""

from __future__ import annotations

STATUS_LABELS = {
    "unchanged": "Unchanged",
    "normal_wear": "Normal wear",
    "damage": "Damage",
    "evolution": "Neutral change",
}

SEVERITY_LABELS = {
    "none": "—",
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}

# Step 5 — present the score without over-promising: one methodology sentence
# in small text, no false precision.
CONFIDENCE_SCORE_CAPTION = (
    "Score computed as the severity-weighted average of model confidence across "
    "all checkpoints. A high score reflects observation consistency, not a "
    "guarantee of accuracy."
)

# Repeated at the footer of each page containing legal qualification elements.
LEGAL_DISCLAIMER = (
    "Indicative AI-generated analysis. Does not replace contradictory expertise "
    "or legal advice. Without a wear grid annexed to the lease, qualification "
    "relies on reasoning by analogy with usual case-law criteria."
)

MISSING_DATA_LABEL = "Data not available"
