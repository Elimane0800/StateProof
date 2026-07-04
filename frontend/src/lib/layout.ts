import { MarkerType, type Edge, type Node } from "reactflow";
import type { Classification, TreeNode } from "../types/contract";

export const NODE_W = 190;
export const NODE_H = 60;

export interface TreeNodeData {
  label: string;
  type: string;
  classification: Classification;
  side: "design" | "code";
  rawId: string;
  depth: number;
}

interface SideLayout {
  nodes: Node<TreeNodeData>[];
  edges: Edge[];
}

function buildSide(root: TreeNode, side: "design" | "code"): SideLayout {
  const parentEdges: Edge[] = [];
  const nodes: Node<TreeNodeData>[] = [];

  const walk = (
    node: TreeNode,
    parent: TreeNode | undefined,
    depth: number,
    siblingIndex: number,
    siblingCount: number,
  ) => {
    const nid = `${side}:${node.id}`;
    const angle = siblingCount > 0 ? (siblingIndex / siblingCount) * Math.PI * 2 : 0;
    const radius = 60 + depth * 55;
    const colCenter = side === "design" ? 280 : 720;
    const rowBase = 120 + depth * 80;
    const cx = colCenter + Math.cos(angle) * radius + (Math.random() - 0.5) * 30;
    const cy = rowBase + Math.sin(angle) * radius * 0.4 + (Math.random() - 0.5) * 30;

    nodes.push({
      id: nid,
      type: "treeNode",
      position: { x: cx - NODE_W / 2, y: cy - NODE_H / 2 },
      data: {
        label: node.label,
        type: node.type,
        classification: node.classification,
        side,
        rawId: node.id,
        depth,
      },
    });

    if (parent) {
      const pid = `${side}:${parent.id}`;
      parentEdges.push({
        id: `e-${pid}-${nid}`,
        source: pid,
        target: nid,
        sourceHandle: "b",
        targetHandle: "t",
        type: "default",
        style: { stroke: "#3a3f4b" },
      });
    }

    const count = node.children.length;
    node.children.forEach((child, i) => walk(child, node, depth + 1, i, count));
  };

  walk(root, undefined, 0, 0, 1);
  return { nodes, edges: parentEdges };
}

function collectIds(root: TreeNode, acc = new Set<string>()): Set<string> {
  acc.add(root.id);
  root.children.forEach((c) => collectIds(c, acc));
  return acc;
}

function extractDetectedLeaves(root: TreeNode, detectedIds: Set<string>): TreeNode[] {
  const result: TreeNode[] = [];
  const seen = new Set<string>();

  const walk = (node: TreeNode) => {
    if (detectedIds.has(node.id) && !seen.has(node.id)) {
      seen.add(node.id);
      result.push({ ...node, children: [] });
    }
    node.children.forEach(walk);
  };

  walk(root);
  return result;
}

function buildDetectedGroup(leaves: TreeNode[], label: string): TreeNode {
  return {
    id: `__detected_${label}`,
    label,
    type: "group",
    classification: "aligned",
    children: leaves,
  };
}

export function filterGraphByDetectedComponents(
  designTree: TreeNode,
  codeTree: TreeNode,
  detectedIds: Set<string>,
): { designTree: TreeNode; codeTree: TreeNode } {
  return {
    designTree: buildDetectedGroup(extractDetectedLeaves(designTree, detectedIds), "Pickup view"),
    codeTree: buildDetectedGroup(extractDetectedLeaves(codeTree, detectedIds), "Return view"),
  };
}

export function buildGraph(design: TreeNode, code: TreeNode) {
  const left = buildSide(design, "design");
  const right = buildSide(code, "code");

  const designIds = collectIds(design);
  const codeIds = collectIds(code);
  const mappingEdges: Edge[] = [];
  for (const id of designIds) {
    if (codeIds.has(id)) {
      mappingEdges.push({
        id: `map-${id}`,
        source: `design:${id}`,
        target: `code:${id}`,
        sourceHandle: "r",
        targetHandle: "l",
        animated: true,
        type: "default",
        style: { stroke: "#6b7280", strokeDasharray: "4 4" },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#6b7280" },
      });
    }
  }

  return {
    nodes: [...left.nodes, ...right.nodes],
    edges: [...left.edges, ...right.edges, ...mappingEdges],
  };
}
