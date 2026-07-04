"""Assemble the (design_tree, code_tree) pair for an audit request."""

from __future__ import annotations

from app.core.schema import AuditRequest, TreeNode
from app.services import code_parser, figma_parser


def build_trees(request: AuditRequest) -> tuple[TreeNode, TreeNode]:
    variant = str(request.tokens.get("variant", "danger"))
    design = figma_parser.design_tree(variant=variant)
    code = code_parser.parse_component(request.code, root_id=design.id, root_label=design.label)
    return design, code
