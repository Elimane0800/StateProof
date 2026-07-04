"""
Agent A — Module de construction de graphe (build_graph, Étape 4).

But : prendre une série d'images (une par checkpoint) et produire un Graph
(LPG) complet, à partir de la config statique des checkpoints (Étape 1).

Ordre de code recommandé : prompts (2) -> nodes.build_node (3, testé isolément)
-> config (1) -> ce fichier (4) -> robustesse (5, déjà dans nodes.build_node).
"""

from __future__ import annotations

from typing import Dict

from langgraph.graph import END, StateGraph

from agents.Agent_A.nodes import build_node, build_nodes_from_image
from agents.Agent_A.state import GraphBuilderState
from agents.common.schemas import EdgeType, Graph, PropertyConfig, StructuralEdge


def build_graph_from_zone_images(config: PropertyConfig, images_by_room: Dict[str, str]) -> Graph:
    """Mode multi-entités : UNE image par zone/pièce (`images_by_room`,
    indexé par nom de room), contenant PLUSIEURS checkpoints à la fois.

    Exemple véhicule : `images_by_room = {"exterieur": "ext.jpg", "interieur": "int.jpg"}`
    avec une config déclarant les checkpoints (pare_choc_avant, portiere...)
    par room dans `PropertyConfig.rooms`. Un seul appel VLM par image (pas
    par checkpoint) — voir `agents.Agent_A.nodes.build_nodes_from_image`.

    Une room sans image associée est ignorée ici — le "trou" est géré en
    aval par le Module C (Étape 6 : "donnée non disponible"), comme pour
    `build_graph`.
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
    """Itère sur tous les checkpoints de la config, construit les Node (LLM)
    et les arêtes structurelles CONTAINS (déterministe, zéro appel LLM).

    `images_by_checkpoint` est indexé par "{room}:{checkpoint_id}". Un
    checkpoint sans image associée est simplement ignoré ici — le "trou"
    sera géré en aval par le Module C (Étape 6 : "donnée non disponible").
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
# Orchestration LangGraph (optionnelle) — homogène avec les autres agents,
# utile si l'on veut brancher Agent_A dans un pipeline LangGraph plus large
# (retries au niveau graphe, streaming de progression, etc.)
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
    # Exemple d'utilisation (à remplir avec de vraies images pour tester)
    config = PropertyConfig.from_json_file("config/checkpoints.example.json")
    images = {
        "salon:mur_nord": "data/appt-12/entry/salon_mur_nord.jpg",
        # ... compléter avec les vraies images disponibles
    }
    result_graph = build_graph(config, images)
    print(result_graph.model_dump_json(indent=2, exclude_none=True))
