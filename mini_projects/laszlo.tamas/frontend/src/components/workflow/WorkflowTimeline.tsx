import { NodeExecution } from "../../types";
import "./WorkflowTimeline.css";

interface WorkflowTimelineProps {
  nodes: NodeExecution[];
  selectedNodeIndex: number;
  onNodeSelect: (index: number) => void;
  onPrev: () => void;
  onNext: () => void;
}

/**
 * Workflow Timeline - Step-by-step navigation
 * 
 * Horizontal timeline with previous/next controls.
 * Shows node execution sequence with visual progress indicator.
 */
export function WorkflowTimeline({
  nodes,
  selectedNodeIndex,
  onNodeSelect,
  onPrev,
  onNext,
}: WorkflowTimelineProps) {
  const canGoPrev = selectedNodeIndex > 0;
  const canGoNext = selectedNodeIndex < nodes.length - 1;

  return (
    <div className="workflow-timeline">
      <div className="timeline-controls">
        <button
          className="timeline-btn"
          onClick={onPrev}
          disabled={!canGoPrev}
          title="Previous node"
        >
          ◀
        </button>

        <div className="timeline-info">
          <span className="timeline-current">
            Step {selectedNodeIndex + 1} / {nodes.length}
          </span>
          <span className="timeline-node-name">
            {nodes[selectedNodeIndex]?.node_name}
          </span>
        </div>

        <button
          className="timeline-btn"
          onClick={onNext}
          disabled={!canGoNext}
          title="Next node"
        >
          ▶
        </button>
      </div>

      <div className="timeline-track">
        {nodes.map((node, index) => (
          <div
            key={index}
            className={`timeline-node ${
              index === selectedNodeIndex ? "selected" : ""
            } ${index < selectedNodeIndex ? "completed" : ""} ${
              node.status === "error" ? "error" : ""
            }`}
            onClick={() => onNodeSelect(index)}
            title={`${node.node_name} (${node.duration_ms.toFixed(0)}ms)`}
          >
            <div className="timeline-dot" />
            <div className="timeline-label">{index + 1}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
