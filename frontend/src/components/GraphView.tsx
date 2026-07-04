import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type NodeMouseHandler,
  type NodeTypes,
} from "reactflow";
import "reactflow/dist/style.css";
import type { AuditPayload } from "../types/contract";
import { buildGraph, type TreeNodeData } from "../lib/layout";
import { TreeNodeCard } from "./TreeNode";

const nodeTypes: NodeTypes = { treeNode: TreeNodeCard };

interface Props {
  audit: AuditPayload;
  selectedNodeId: string | null;
  onSelectNode: (rawId: string) => void;
}

export function GraphView({ audit, selectedNodeId, onSelectNode }: Props) {
  const { nodes, edges } = useMemo(
    () => buildGraph(audit.design_tree, audit.code_tree),
    [audit]
  );

  const decorated: Node<TreeNodeData>[] = nodes.map((n) => ({
    ...n,
    selected: n.data.rawId === selectedNodeId,
  }));

  const handleClick: NodeMouseHandler = (_evt, node) => {
    onSelectNode((node.data as TreeNodeData).rawId);
  };

  return (
    <div className="graph-view">
      <div className="graph-view__headers">
        <span>Design intent (Figma)</span>
        <span>Implementation (code)</span>
      </div>
      <ReactFlow
        nodes={decorated}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleClick}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} color="#1f2430" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
