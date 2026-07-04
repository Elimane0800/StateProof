"""Pydantic models mirroring packages/contract/schema.json.

This is the single Python representation of the frozen JSON contract. Every
response the backend emits validates against these models, guaranteeing the PR
comment, the Studio, and the metrics script all read the same shape.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Classification(str, Enum):
    ALIGNED = "aligned"
    DESIGN_VIOLATION = "design_violation"
    TECHNICAL_NOISE = "technical_noise"
    INTENTIONAL_EVOLUTION = "intentional_evolution"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TreeNode(BaseModel):
    id: str
    label: str
    type: str
    classification: Classification = Classification.ALIGNED
    props: dict[str, Any] = Field(default_factory=dict)
    children: List["TreeNode"] = Field(default_factory=list)


TreeNode.model_rebuild()


class CursorPatch(BaseModel):
    prompt: str
    diff: str


class Finding(BaseModel):
    type: str
    classification: Classification
    severity: Severity
    location: str
    node_id: str
    bbox: Optional[List[float]] = None
    expected: str
    actual: str
    reasoning: str
    cursor_patch: CursorPatch


class NoiseItem(BaseModel):
    element: str
    node_id: Optional[str] = None
    reasoning: str


class EvolutionProposal(BaseModel):
    element: str
    node_id: Optional[str] = None
    reasoning: str
    proposal: str


class AuditPayload(BaseModel):
    """The frozen contract. Response of POST /audit and GET /report/{id}."""

    audit_id: str
    pr_number: int
    drift_score: int = Field(ge=0, le=100)
    screenshot_url: str
    design_tree: TreeNode
    code_tree: TreeNode
    findings: List[Finding] = Field(default_factory=list)
    ignored_as_noise: List[NoiseItem] = Field(default_factory=list)
    evolution_proposals: List[EvolutionProposal] = Field(default_factory=list)


class AuditRequest(BaseModel):
    """Input to POST /audit from the GitHub Action (R4)."""

    pr_number: int
    run: int = 1
    file_path: str = "StatusCard.tsx"
    code: str = Field(..., description="Source of the changed component.")
    screenshot_url: Optional[str] = None
    screenshot_b64: Optional[str] = Field(
        default=None, description="Base64 PNG of the CI-rendered component."
    )
    tokens: dict[str, Any] = Field(
        default_factory=dict, description="The design tokens the code should honor."
    )


class FixRequest(BaseModel):
    """Input to POST /fix from the Studio prompt box (R5)."""

    audit_id: str
    node_id: str
    prompt: str = Field(..., description="Natural-language change request.")


class FixResponse(BaseModel):
    node_id: str
    cursor_patch: CursorPatch
