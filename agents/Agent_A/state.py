"""Agent A — Shared state for the LPG graph-construction LangGraph."""

from __future__ import annotations

from typing import Dict, List, TypedDict

from agents.common.schemas import Graph, PropertyConfig


class GraphBuilderState(TypedDict, total=False):
    # Inputs
    config: PropertyConfig
    # key = "{room}:{checkpoint_id}" -> checkpoint image path
    images_by_checkpoint: Dict[str, str]

    # Outputs
    graph: Graph
    errors: List[str]
