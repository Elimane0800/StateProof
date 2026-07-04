import { useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Node,
  type NodeMouseHandler,
  type NodeTypes,
} from "reactflow";
import "reactflow/dist/style.css";
import type { AuditPayload } from "../types/contract";
import { useForceLayout } from "../hooks/useForceLayout";
import { buildGraph, filterGraphByDetectedComponents, type TreeNodeData } from "../lib/layout";
import { TreeNodeCard } from "./TreeNode";

const nodeTypes: NodeTypes = { treeNode: TreeNodeCard };

interface Props {
  audit: AuditPayload;
  selectedNodeId: string | null;
  onSelectNode: (rawId: string) => void;
  detectedComponentIds?: Set<string> | null;
}

function GraphViewInner({ audit, selectedNodeId, onSelectNode, detectedComponentIds }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const fitOnce = useRef(false);
  const { fitView } = useReactFlow();

  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(() => {
    if (detectedComponentIds && detectedComponentIds.size > 0) {
      const filtered = filterGraphByDetectedComponents(
        audit.design_tree,
        audit.code_tree,
        detectedComponentIds,
      );
      return buildGraph(filtered.designTree, filtered.codeTree);
    }
    return buildGraph(audit.design_tree, audit.code_tree);
  }, [audit, detectedComponentIds]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, , onEdgesChange] = useEdgesState(layoutEdges);

  useEffect(() => {
    setNodes(layoutNodes);
    fitOnce.current = false;
  }, [layoutNodes, setNodes]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setContainerWidth(entry.contentRect.width);
    });
    ro.observe(el);
    setContainerWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const { onNodeDragStart, onNodeDrag, onNodeDragStop } = useForceLayout(
    layoutNodes,
    layoutEdges,
    containerWidth,
    setNodes,
  );

  useEffect(() => {
    if (fitOnce.current || layoutNodes.length === 0 || containerWidth <= 0) return;
    const timer = window.setTimeout(() => {
      fitView({ padding: 0.15, duration: 400 });
      fitOnce.current = true;
    }, 900);
    return () => window.clearTimeout(timer);
  }, [layoutNodes.length, containerWidth, fitView]);

  const decorated: Node<TreeNodeData>[] = nodes.map((n) => ({
    ...n,
    selected: n.data.rawId === selectedNodeId,
  }));

  const handleClick: NodeMouseHandler = (_evt, node) => {
    onSelectNode((node.data as TreeNodeData).rawId);
  };

  return (
    <div ref={containerRef} className="graph-view">
      <div className="graph-view__headers">
        <span>Pickup</span>
        <span>Return</span>
        {detectedComponentIds && detectedComponentIds.size > 0 && (
          <span className="graph-view__filter-badge">
            {detectedComponentIds.size} detected in return media
          </span>
        )}
      </div>
      <ReactFlow
        nodes={decorated}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleClick}
        onNodeDragStart={onNodeDragStart}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        nodesDraggable
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

export function GraphView(props: Props) {
  return (
    <ReactFlowProvider>
      <GraphViewInner {...props} />
    </ReactFlowProvider>
  );
}
