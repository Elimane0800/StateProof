"""Produce the design_tree - the Figma intent for the hero component.

For the hackathon the Figma intent is hardcoded (frozen scope: no dynamic
Figma scraper). It expresses the *canonical* StatusCard using design tokens, so
the classifier can compare it against the parsed code_tree. Node ids are stable
and shared with code_parser output.
"""

from __future__ import annotations

from app.core.schema import Classification, TreeNode


def design_tree(variant: str = "danger") -> TreeNode:
    accent = f"color-{variant}" if variant in {"danger", "warning", "primary"} else "color-primary"
    return TreeNode(
        id="card",
        label="StatusCard",
        type="container",
        classification=Classification.ALIGNED,
        props={"variant": variant, "radius": "radius-md", "padding": "spacing-md"},
        children=[
            TreeNode(
                id="icon",
                label="Icon",
                type="icon",
                classification=Classification.ALIGNED,
                props={"color": accent},
            ),
            TreeNode(
                id="content",
                label="Content",
                type="container",
                classification=Classification.ALIGNED,
                props={"gap": "spacing-sm"},
                children=[
                    TreeNode(
                        id="title",
                        label="Title",
                        type="text",
                        classification=Classification.ALIGNED,
                        props={"font": "font-heading", "color": "color-text"},
                    ),
                    TreeNode(
                        id="description",
                        label="Description",
                        type="text",
                        classification=Classification.ALIGNED,
                        props={"font": "font-body", "color": "color-text"},
                    ),
                ],
            ),
            TreeNode(
                id="btn-primary",
                label="Action Button",
                type="button",
                classification=Classification.ALIGNED,
                props={"background": accent, "radius": "radius-md", "padding": "spacing-md"},
            ),
        ],
    )
