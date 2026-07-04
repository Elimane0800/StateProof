import { Handle, Position, type NodeProps } from "reactflow";
import type { Classification } from "../types/contract";
import type { TreeNodeData } from "../lib/layout";

export const CLASS_COLORS: Record<Classification, { border: string; bg: string; label: string }> = {
  aligned: { border: "#22c55e", bg: "rgba(34,197,94,0.12)", label: "Aligned" },
  design_violation: { border: "#ef4444", bg: "rgba(239,68,68,0.14)", label: "Violation" },
  technical_noise: { border: "#6b7280", bg: "rgba(107,114,128,0.14)", label: "Noise (ignored)" },
  intentional_evolution: { border: "#f59e0b", bg: "rgba(245,158,11,0.14)", label: "Evolution" },
};

export function TreeNodeCard({ data, selected }: NodeProps<TreeNodeData>) {
  const c = CLASS_COLORS[data.classification];
  return (
    <div
      className="tree-node"
      style={{
        borderColor: c.border,
        background: c.bg,
        boxShadow: selected ? `0 0 0 2px ${c.border}` : undefined,
      }}
    >
      <Handle id="t" type="target" position={Position.Top} />
      <Handle id="l" type="target" position={Position.Left} />
      <div className="tree-node__label">{data.label}</div>
      <div className="tree-node__meta">
        <span className="tree-node__type">{data.type}</span>
        <span className="tree-node__dot" style={{ background: c.border }} />
      </div>
      <Handle id="b" type="source" position={Position.Bottom} />
      <Handle id="r" type="source" position={Position.Right} />
    </div>
  );
}
