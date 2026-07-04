"""Agent A — State partagé par le graphe LangGraph de construction du graphe LPG."""

from __future__ import annotations

from typing import Dict, List, TypedDict

from agents.common.schemas import Graph, PropertyConfig


class GraphBuilderState(TypedDict, total=False):
    # Entrées
    config: PropertyConfig
    # clé = "{room}:{checkpoint_id}" -> chemin de l'image du checkpoint
    images_by_checkpoint: Dict[str, str]

    # Sorties
    graph: Graph
    errors: List[str]
