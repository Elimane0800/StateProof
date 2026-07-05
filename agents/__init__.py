"""
ARIA — 4-module agentic pipeline.

Module A (Agent_A.build_graph)  -> entry_graph, exit_graph
Module B (Agent_B.align)        -> list[AlignmentEdge] + confidence_score
Module D (Agent_D.qualify)      -> LegalQualification per "damage" AlignmentEdge
Module C (Agent_C.build_report) -> rapport.pdf

Each arrow is a data contract (agents.common.schemas), not shared code: the 4
modules can be coded and tested independently, each against mocks of the others.
"""
