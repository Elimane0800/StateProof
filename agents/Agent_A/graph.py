"""
Agent A — Graph construction module (build_graph, step 4).

Goal: take a series of images (one per checkpoint) and produce a complete `Graph`
(LPG) from the static checkpoint config (step 1).

Recommended code order: prompts (2) -> nodes.build_node (3, tested in isolation)
-> config (1) -> this file (4) -> robustness (5, already in nodes.build_node).
"""

from __future__ import annotations

from typing import Dict

from langgraph.graph import END, StateGraph

from agents.Agent_A.nodes import build_node, build_nodes_from_image
from agents.Agent_A.state import GraphBuilderState
from agents.common.schemas import EdgeType, Graph, PropertyConfig, StructuralEdge


def build_graph_from_zone_images(config: PropertyConfig, images_by_room: Dict[str, str]) -> Graph:
    """Multi-entity mode: ONE image per zone/room (`images_by_room`, indexed by
    room name), containing SEVERAL checkpoints at once.

    Vehicle example: `images_by_room = {"exterieur": "ext.jpg", "interieur": "int.jpg"}`
    with a config declaring checkpoints (pare_choc_avant, portiere...) per room
    in `PropertyConfig.rooms`. One VLM call per image (not per checkpoint) — see
    `agents.Agent_A.nodes.build_nodes_from_image`.

    A room without an associated image is skipped here — the gap is handled
    downstream by Module C (step 6: "data not available"), same as `build_graph`.
    """
    graph = Graph(property_id=config.property_id)

    for room_name, room_config in config.rooms.items():
        room_node_id = f"room:{room_name}"
        image_path = images_by_room.get(room_name)
        if image_path is None:
            continue

        checkpoints = room_config.normalized_checkpoints()
        nodes = build_nodes_from_image(image_path=image_path, checkpoints=checkpoints, room=room_name)

        for node in nodes:
            graph.nodes[node.id] = node
            graph.edges.append(
                StructuralEdge(source=room_node_id, target=node.id, type=EdgeType.CONTAINS)
            )

    return graph


def build_graph(config: PropertyConfig, images_by_checkpoint: Dict[str, str]) -> Graph:
    """Iterate over all checkpoints in the config, build Nodes (LLM) and
    deterministic CONTAINS structural edges (zero LLM calls).

    `images_by_checkpoint` is indexed by "{room}:{checkpoint_id}". A checkpoint
    without an associated image is simply skipped here — the gap is handled
    downstream by Module C (step 6: "data not available").
    """
    graph = Graph(property_id=config.property_id)

    for room_name, room_config in config.rooms.items():
        room_node_id = f"room:{room_name}"

        for checkpoint in room_config.normalized_checkpoints():
            key = f"{room_name}:{checkpoint.id}"
            image_path = images_by_checkpoint.get(key)
            if image_path is None:
                continue

            node = build_node(
                image_path=image_path,
                checkpoint_id=checkpoint.id,
                room=room_name,
                element_type=checkpoint.element_type,
            )
            graph.nodes[node.id] = node
            graph.edges.append(
                StructuralEdge(source=room_node_id, target=node.id, type=EdgeType.CONTAINS)
            )

    return graph


# ---------------------------------------------------------------------------
# Optional LangGraph orchestration — consistent with other agents; useful to
# plug Agent_A into a larger LangGraph pipeline (graph-level retries, progress
# streaming, etc.)
# ---------------------------------------------------------------------------

def _build_graph_step(state: GraphBuilderState) -> GraphBuilderState:
    graph = build_graph(state["config"], state["images_by_checkpoint"])
    return {**state, "graph": graph}


def compile_agent_a_graph():
    workflow = StateGraph(GraphBuilderState)
    workflow.add_node("build_graph", _build_graph_step)
    workflow.set_entry_point("build_graph")
    workflow.add_edge("build_graph", END)
    return workflow.compile()


if __name__ == "__main__":
    # Usage example (fill with real images to test)
    config = PropertyConfig.from_json_file("config/checkpoints.example.json")
    images = {
        "salon:mur_nord": "data/appt-12/entry/salon_mur_nord.jpg",
        # ... complete with available real images
    }
    result_graph = build_graph(config, images)
    print(result_graph.model_dump_json(indent=2, exclude_none=True))
