"""
ARIA — Pipeline agentique en 4 modules.

Module A (Agent_A.build_graph)  -> entry_graph, exit_graph
Module B (Agent_B.align)        -> list[AlignmentEdge] + confidence_score
Module D (Agent_D.qualify)      -> LegalQualification par AlignmentEdge "damage"
Module C (Agent_C.build_report) -> rapport.pdf

Chaque flèche est un contrat de données (agents.common.schemas), pas de code
partagé : les 4 modules sont codables et testables indépendamment, chacun
contre des mocks des autres.
"""
