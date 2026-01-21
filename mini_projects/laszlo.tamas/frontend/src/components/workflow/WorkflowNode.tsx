import { memo } from "react";
import { Handle, Position } from "reactflow";
import "./WorkflowNode.css";

interface WorkflowNodeProps {
  data: {
    nodeName: string;
    duration: number;
    status: "success" | "error" | "skipped";
    isSelected: boolean;
    onClick: () => void;
  };
}

/**
 * Custom React Flow node for workflow visualization.
 * Displays node name, duration, and status with color coding.
 */
export const WorkflowNode = memo(({ data }: WorkflowNodeProps) => {
  const { nodeName, duration, status, isSelected, onClick } = data;

  const getStatusIcon = () => {
    switch (status) {
      case "success":
        return "✓";
      case "error":
        return "✗";
      case "skipped":
        return "−";
      default:
        return "○";
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case "success":
        return "#22c55e";
      case "error":
        return "#ef4444";
      case "skipped":
        return "#94a3b8";
      default:
        return "#64748b";
    }
  };

  return (
    <div
      className={`workflow-node ${status} ${isSelected ? "selected" : ""}`}
      onClick={onClick}
      style={{ borderColor: isSelected ? "#3b82f6" : getStatusColor() }}
    >
      <Handle type="target" position={Position.Top} />

      <div className="node-header">
        <span
          className="node-status-icon"
          style={{ color: getStatusColor() }}
        >
          {getStatusIcon()}
        </span>
        <span className="node-name">{nodeName}</span>
      </div>

      <div className="node-duration">{duration.toFixed(0)}ms</div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
});

WorkflowNode.displayName = "WorkflowNode";
