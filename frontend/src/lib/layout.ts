import dagre from "dagre";
import { MarkerType, type Edge, type Node } from "reactflow";
import type { Classification, TreeNode } from "../types/contract";

export const NODE_W = 190;
export const NODE_H = 60;
const SIDE_GAP = 220;

export interface TreeNodeData {
  label: string;
  type: string;
  classification: Classification;
  side: "design" | "code";
  rawId: string;
}

interface SideLayout {
  nodes: Node<TreeNodeData>[];
  edges: Edge[];
  width: number;
}

function layoutSide(root: TreeNode, side: "design" | "code", xOffset: number): SideLayout {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 24, ranksep: 64, marginx: 16, marginy: 16 });
  g.setDefaultEdgeLabel(() => ({}));

  const parentEdges: Edge[] = [];

  const walk = (node: TreeNode, parent?: TreeNode) => {
    const nid = `${side}:${node.id}`;
    g.setNode(nid, { width: NODE_W, height: NODE_H });
    if (parent) {
      const pid = `${side}:${parent.id}`;
      g.setEdge(pid, nid);
      parentEdges.push({
        id: `e-${pid}-${nid}`,
        source: pid,
        target: nid,
        sourceHandle: "b",
        targetHandle: "t",
        type: "smoothstep",
        style: { stroke: "#3a3f4b" },
      });
    }
    node.children.forEach((child) => walk(child, node));
  };
  walk(root);

  dagre.layout(g);

  const nodes: Node<TreeNodeData>[] = [];
  let width = 0;
  const collect = (node: TreeNode) => {
    const nid = `${side}:${node.id}`;
    const pos = g.node(nid);
    width = Math.max(width, pos.x + NODE_W);
    nodes.push({
      id: nid,
      type: "treeNode",
      position: { x: pos.x - NODE_W / 2 + xOffset, y: pos.y - NODE_H / 2 },
      data: { label: node.label, type: node.type, classification: node.classification, side, rawId: node.id },
    });
    node.children.forEach(collect);
  };
  collect(root);

  return { nodes, edges: parentEdges, width };
}

function collectIds(root: TreeNode, acc = new Set<string>()): Set<string> {
  acc.add(root.id);
  root.children.forEach((c) => collectIds(c, acc));
  return acc;
}

export function buildGraph(design: TreeNode, code: TreeNode) {
  const left = layoutSide(design, "design", 0);
  const right = layoutSide(code, "code", left.width + SIDE_GAP);

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
