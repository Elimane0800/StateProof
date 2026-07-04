import { useCallback, useEffect, useRef } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import type { Edge, Node } from "reactflow";
import { NODE_H, NODE_W, type TreeNodeData } from "../lib/layout";

interface SimNode extends SimulationNodeDatum {
  id: string;
  side: "design" | "code";
  depth: number;
}

interface SimLink extends SimulationLinkDatum<SimNode> {
  kind: "tree" | "mapping";
}

const CHARGE = -550;
const LINK_DIST_TREE = 90;
const LINK_DIST_MAP = 200;
const LINK_STRENGTH_TREE = 0.85;
const LINK_STRENGTH_MAP = 0.35;
const COLLIDE_RADIUS = 70;
const VELOCITY_DECAY = 0.3;
const ALPHA_TARGET = 0.04;
const FORCE_X_STRENGTH = 0.12;
const FORCE_Y_STRENGTH = 0.08;
const DESIGN_X_RATIO = 0.28;
const CODE_X_RATIO = 0.72;

export function useForceLayout(
  layoutNodes: Node<TreeNodeData>[],
  edges: Edge[],
  width: number,
  setNodes: React.Dispatch<React.SetStateAction<Node<TreeNodeData>[]>>,
) {
  const simRef = useRef<Simulation<SimNode, SimLink> | null>(null);
  const nodeMapRef = useRef<Map<string, SimNode>>(new Map());
  const setNodesRef = useRef(setNodes);
  setNodesRef.current = setNodes;

  useEffect(() => {
    if (width <= 0 || layoutNodes.length === 0) return;

    const simNodes: SimNode[] = layoutNodes.map((n) => ({
      id: n.id,
      side: n.data.side,
      depth: n.data.depth,
      x: n.position.x + NODE_W / 2,
      y: n.position.y + NODE_H / 2,
    }));
    const nodeById = new Map(simNodes.map((n) => [n.id, n]));
    nodeMapRef.current = nodeById;

    const links: SimLink[] = [];
    for (const e of edges) {
      const source = nodeById.get(e.source);
      const target = nodeById.get(e.target);
      if (source && target) {
        links.push({
          source,
          target,
          kind: e.id.startsWith("map-") ? "mapping" : "tree",
        });
      }
    }

    const sim = forceSimulation(simNodes)
      .velocityDecay(VELOCITY_DECAY)
      .alphaTarget(ALPHA_TARGET)
      .force(
        "link",
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance((d) => (d.kind === "mapping" ? LINK_DIST_MAP : LINK_DIST_TREE))
          .strength((d) => (d.kind === "mapping" ? LINK_STRENGTH_MAP : LINK_STRENGTH_TREE)),
      )
      .force("charge", forceManyBody<SimNode>().strength(CHARGE))
      .force("collide", forceCollide<SimNode>(COLLIDE_RADIUS))
      .force(
        "x",
        forceX<SimNode>()
          .x((d) => (d.side === "design" ? width * DESIGN_X_RATIO : width * CODE_X_RATIO))
          .strength(FORCE_X_STRENGTH),
      )
      .force(
        "y",
        forceY<SimNode>()
          .y((d) => 80 + d.depth * 90)
          .strength(FORCE_Y_STRENGTH),
      )
      .force("center", forceCenter(width / 2, 280).strength(0.02))
      .on("tick", () => {
        setNodesRef.current((current) =>
          current.map((node) => {
            const simNode = nodeById.get(node.id);
            if (!simNode || simNode.x == null || simNode.y == null) return node;
            return {
              ...node,
              position: {
                x: simNode.x - NODE_W / 2,
                y: simNode.y - NODE_H / 2,
              },
            };
          }),
        );
      });

    simRef.current = sim;

    return () => {
      sim.stop();
      simRef.current = null;
    };
  }, [layoutNodes, edges, width]);

  const onNodeDragStart = useCallback((_evt: React.MouseEvent, node: Node<TreeNodeData>) => {
    const simNode = nodeMapRef.current.get(node.id);
    if (!simNode) return;
    simNode.fx = node.position.x + NODE_W / 2;
    simNode.fy = node.position.y + NODE_H / 2;
    simRef.current?.alphaTarget(ALPHA_TARGET).restart();
  }, []);

  const onNodeDrag = useCallback((_evt: React.MouseEvent, node: Node<TreeNodeData>) => {
    const simNode = nodeMapRef.current.get(node.id);
    if (!simNode) return;
    simNode.fx = node.position.x + NODE_W / 2;
    simNode.fy = node.position.y + NODE_H / 2;
  }, []);

  const onNodeDragStop = useCallback((_evt: React.MouseEvent, node: Node<TreeNodeData>) => {
    const simNode = nodeMapRef.current.get(node.id);
    if (!simNode) return;
    simNode.fx = null;
    simNode.fy = null;
    simRef.current?.alpha(0.3).restart();
  }, []);

  return { onNodeDragStart, onNodeDrag, onNodeDragStop };
}
