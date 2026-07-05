"""
ARIA — Shared schemas (the "data contract" between modules A, B, C, D).

This file should be frozen first: Module B depends only on `Node` (produced by
Module A), Module C only on `AlignmentEdge` and `Node`, Module D only on
`AlignmentEdge`. No module knows other modules' internals — only these structures.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Checkpoint config (Module A — step 1)
# Static JSON file, no LLM dependency. See config/checkpoints.example.json
# ---------------------------------------------------------------------------

class CheckpointDef(BaseModel):
    """A checkpoint = one physical element to observe (a wall, floor...)."""

    id: str
    element_type: Optional[str] = None  # "mur", "sol", "prise_electrique"...


class RoomConfig(BaseModel):
    """Checkpoint list for one room.

    Accepts either a list of simple strings (cf. brief example) or a list of
    `CheckpointDef` if you want to specify `element_type` explicitly rather than
    inferring it from the name.
    """

    checkpoints: List[Union[str, CheckpointDef]]

    def normalized_checkpoints(self) -> List[CheckpointDef]:
        normalized: List[CheckpointDef] = []
        for cp in self.checkpoints:
            if isinstance(cp, CheckpointDef):
                normalized.append(cp)
            else:
                normalized.append(CheckpointDef(id=cp, element_type=_guess_element_type(cp)))
        return normalized


class PropertyConfig(BaseModel):
    """Fixed skeleton for a property: property_id + rooms + checkpoints."""

    property_id: str
    rooms: Dict[str, RoomConfig]

    @classmethod
    def from_json_file(cls, path: str) -> "PropertyConfig":
        import json

        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate(json.load(f))


def _guess_element_type(checkpoint_id: str) -> Optional[str]:
    """Simple heuristic when `element_type` is not provided explicitly."""
    lowered = checkpoint_id.lower()
    guesses = {
        "mur": "mur",
        "plafond": "plafond",
        "sol": "sol",
        "sol_carrelage": "sol",
        "prise": "prise_electrique",
        "porte": "porte",
        "fenetre": "fenetre",
        "radiateur": "radiateur",
        "robinet": "robinetterie",
        "evier": "sanitaire",
        "wc": "sanitaire",
        "baignoire": "sanitaire",
    }
    for key, value in guesses.items():
        if key in lowered:
            return value
    return None


# ---------------------------------------------------------------------------
# Node (Module A — steps 2 & 3) — central contract for the whole pipeline
# ---------------------------------------------------------------------------

class NodeProperties(BaseModel):
    """Strict JSON output of the state-description prompt (one image)."""

    material: Optional[str] = None
    color: Optional[str] = None
    condition: str = "unknown"  # "intact" | "usé" | "endommagé" | "unknown"
    defects: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class Node(BaseModel):
    """A graph node = one checkpoint observed at one moment (entry or exit).

    `image_path` is NOT necessarily unique per node: in multi-entity mode (one
    photo contains several checkpoints, e.g. vehicle exterior showing bumper +
    door + wheel), several `Node`s may share the same image. `bbox_pct` then
    localizes THIS checkpoint inside that shared image (normalized coordinates
    [x_min, y_min, x_max, y_max]) so Module B knows where to look without
    confusing defects from neighboring checkpoints.
    """

    id: str  # convention: "{room}:{checkpoint_id}"
    checkpoint_id: str
    room: str
    element_type: Optional[str] = None
    image_path: Optional[str] = None
    bbox_pct: Optional[List[float]] = None
    visible: bool = True
    properties: NodeProperties
    extraction_failed: bool = False


# ---------------------------------------------------------------------------
# Graph (LPG) — structural edges, deterministic, zero LLM calls
# ---------------------------------------------------------------------------

class EdgeType(str, Enum):
    CONTAINS = "CONTAINS"


class StructuralEdge(BaseModel):
    source: str
    target: str
    type: EdgeType = EdgeType.CONTAINS


class Graph(BaseModel):
    property_id: str
    nodes: Dict[str, Node] = Field(default_factory=dict)
    edges: List[StructuralEdge] = Field(default_factory=list)

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def checkpoint_node_ids(self) -> set:
        return set(self.nodes.keys())


# ---------------------------------------------------------------------------
# AlignmentEdge (Module B) — `status` enum is frozen now; everything else
# (Studio colors, PDF filters) depends on it.
# ---------------------------------------------------------------------------

class AlignmentStatus(str, Enum):
    UNCHANGED = "unchanged"
    NORMAL_WEAR = "normal_wear"
    DAMAGE = "damage"
    EVOLUTION = "evolution"


class Severity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlignmentEdge(BaseModel):
    """Result of comparing the same checkpoint between entry and exit."""

    node_id: str  # "{room}:{checkpoint_id}", common to both graphs
    checkpoint_id: str
    room: str
    status: AlignmentStatus
    severity: Severity = Severity.NONE
    confidence: float = 0.0
    reasoning: str = ""
    estimated_cost_eur: float = 0.0
    comparison_failed: bool = False  # Module C step 6: show "data not available"
    # Divergence zone localized by VLM, normalized [0,1] coordinates
    # [x_min, y_min, x_max, y_max] on the image. None if status="unchanged" or
    # if the model could not localize precisely.
    bbox_pct: Optional[List[float]] = None


# ---------------------------------------------------------------------------
# Module D — legal qualification (wear vs abnormal use)
# ---------------------------------------------------------------------------

class VetusteGridEntry(BaseModel):
    """One row of a contractual wear grid (annexed to lease)."""

    duree_vie_ans: float
    franchise_ans: float
    taux_annuel: float  # e.g. 0.10 => 10%/year deduction


VetusteGrid = Dict[str, VetusteGridEntry]  # key = element_category


class LegalQualification(BaseModel):
    legal_qualification: str  # "vetuste" | "degradation_locative" | "usage_normal" | "indetermine"
    responsibility: str  # "locataire" | "bailleur" | "indetermine"
    legal_basis: List[str] = Field(default_factory=list)
    grille_appliquee: bool = False
    abattement_pct: Optional[float] = None
    chargeable_amount_eur: Optional[float] = None
    reasoning: str = ""
    confidence: float = 0.0
    disclaimer: str = (
        "Indicative AI-generated analysis; does not replace contradictory "
        "expertise or legal advice."
    )


# ---------------------------------------------------------------------------
# Module C — report render structures (prepared by prepare_report_data)
# ---------------------------------------------------------------------------

class SummaryRow(BaseModel):
    checkpoint_id: str
    room: str
    status: str
    severity: str
    cost_eur: float
    responsibility: Optional[str] = None
    data_available: bool = True


class DetailedSection(BaseModel):
    checkpoint_id: str
    room: str
    entry_image_path: Optional[str] = None
    exit_image_path: Optional[str] = None
    composite_image_path: Optional[str] = None
    reasoning: str = ""
    legal: Optional[LegalQualification] = None
    cost_eur: float = 0.0
    data_available: bool = True


class ReportData(BaseModel):
    property_id: str
    address: Optional[str] = None
    entry_date: Optional[str] = None
    exit_date: Optional[str] = None
    confidence_score: float = 0.0
    confidence_score_method: str = (
        "Severity-weighted average across all checkpoints."
    )
    summary_rows: List[SummaryRow] = Field(default_factory=list)
    detailed_sections: List[DetailedSection] = Field(default_factory=list)
    unchanged_checkpoints: List[str] = Field(default_factory=list)
    total_cost_eur: float = 0.0
    negotiation_points: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "Indicative AI-generated analysis; does not replace contradictory "
        "expertise or legal advice."
    )
