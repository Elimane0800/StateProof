"""
ARIA — Schémas partagés (le "contrat de données" entre les modules A, B, C, D).

Ce fichier doit être figé en premier : Module B ne dépend que de `Node`
(produit par Module A), Module C ne dépend que de `AlignmentEdge` et `Node`,
Module D ne dépend que de `AlignmentEdge`. Aucun module ne connaît les
détails internes des autres — uniquement ces structures.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Config des checkpoints (Module A — Étape 1)
# Fichier statique JSON, ne dépend d'aucun LLM. Voir config/checkpoints.example.json
# ---------------------------------------------------------------------------

class CheckpointDef(BaseModel):
    """Un checkpoint = un élément physique à observer (un mur, un sol...)."""

    id: str
    element_type: Optional[str] = None  # "mur", "sol", "prise_electrique"...


class RoomConfig(BaseModel):
    """Liste des checkpoints d'une pièce.

    Accepte soit une liste de chaînes simples (cf. exemple du brief),
    soit une liste de `CheckpointDef` si on veut préciser `element_type`
    explicitement plutôt que de le déduire du nom.
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
    """Le squelette fixe d'un bien : property_id + pièces + checkpoints."""

    property_id: str
    rooms: Dict[str, RoomConfig]

    @classmethod
    def from_json_file(cls, path: str) -> "PropertyConfig":
        import json

        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate(json.load(f))


def _guess_element_type(checkpoint_id: str) -> Optional[str]:
    """Heuristique simple si `element_type` n'est pas fourni explicitement."""
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
# Node (Module A — Étape 2 & 3) — le contrat central de tout le pipeline
# ---------------------------------------------------------------------------

class NodeProperties(BaseModel):
    """Sortie JSON stricte du prompt de description d'état (une image)."""

    material: Optional[str] = None
    color: Optional[str] = None
    condition: str = "unknown"  # "intact" | "usé" | "endommagé" | "unknown"
    defects: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class Node(BaseModel):
    """Un nœud du graphe = un checkpoint observé à un instant donné (entrée ou sortie).

    `image_path` n'est PAS forcément unique par nœud : en mode multi-entités
    (une photo contient plusieurs checkpoints, ex. une photo d'extérieur de
    véhicule montrant pare-choc + portière + jante), plusieurs `Node` peuvent
    partager la même image. `bbox_pct` localise alors CE checkpoint précis
    à l'intérieur de cette image partagée (coordonnées normalisées
    [x_min, y_min, x_max, y_max]), pour que le Module B sache où regarder
    sans confondre les défauts de checkpoints voisins.
    """

    id: str  # convention : "{room}:{checkpoint_id}"
    checkpoint_id: str
    room: str
    element_type: Optional[str] = None
    image_path: Optional[str] = None
    bbox_pct: Optional[List[float]] = None
    visible: bool = True
    properties: NodeProperties
    extraction_failed: bool = False


# ---------------------------------------------------------------------------
# Graph (LPG) — arêtes structurelles, déterministes, zéro appel LLM
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
# AlignmentEdge (Module B) — l'énumération `status` est figée dès maintenant,
# tout le reste (couleurs Studio, filtres PDF) en dépend.
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
    """Résultat de la comparaison d'un même checkpoint entre entrée et sortie."""

    node_id: str  # "{room}:{checkpoint_id}", commun aux deux graphes
    checkpoint_id: str
    room: str
    status: AlignmentStatus
    severity: Severity = Severity.NONE
    confidence: float = 0.0
    reasoning: str = ""
    estimated_cost_eur: float = 0.0
    comparison_failed: bool = False  # Étape 6 Module C : afficher "donnée non disponible"
    # Zone de divergence localisée par le VLM, coordonnées normalisées [0,1]
    # [x_min, y_min, x_max, y_max] sur l'image. None si status="unchanged" ou
    # si le modèle n'a pas pu localiser précisément l'anomalie.
    bbox_pct: Optional[List[float]] = None


# ---------------------------------------------------------------------------
# Module D — qualification légale (vétusté vs usage anormal)
# ---------------------------------------------------------------------------

class VetusteGridEntry(BaseModel):
    """Une ligne de grille de vétusté contractuelle (annexée au bail)."""

    duree_vie_ans: float
    franchise_ans: float
    taux_annuel: float  # ex : 0.10 => 10 %/an d'abattement


VetusteGrid = Dict[str, VetusteGridEntry]  # clé = element_category


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
        "Analyse indicative générée par IA, ne remplace pas une expertise "
        "contradictoire ou un avis juridique."
    )


# ---------------------------------------------------------------------------
# Module C — structures de rendu du rapport (préparées par prepare_report_data)
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
        "Moyenne pondérée par sévérité sur l'ensemble des points de contrôle."
    )
    summary_rows: List[SummaryRow] = Field(default_factory=list)
    detailed_sections: List[DetailedSection] = Field(default_factory=list)
    unchanged_checkpoints: List[str] = Field(default_factory=list)
    total_cost_eur: float = 0.0
    negotiation_points: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "Analyse indicative générée par IA, ne remplace pas une expertise "
        "contradictoire ou un avis juridique."
    )
