import { useEffect, useState } from "react";
import { WorkflowExecution, NodeExecution } from "../../types";
import { fetchWorkflowExecution, fetchNodeExecutions } from "../../api";
import { WorkflowGraph } from "./WorkflowGraph";
import { NodeDetailsPanel } from "./NodeDetailsPanel";
import { WorkflowTimeline } from "./WorkflowTimeline";
import "./WorkflowModal.css";

interface WorkflowModalProps {
  executionId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Workflow Visualizer Modal - Left side slide-in panel
 * 
 * Displays workflow execution graph with step-by-step debugging.
 * User clicks on LLM message → modal opens → graph renders → node inspection.
 * 
 * Architecture:
 * - WorkflowGraph: react-flow node/edge rendering
 * - NodeDetailsPanel: input/output state inspection
 * - WorkflowTimeline: step-by-step navigation
 */
export function WorkflowModal({ executionId, isOpen, onClose }: WorkflowModalProps) {
  const [workflow, setWorkflow] = useState<WorkflowExecution | null>(null);
  const [nodes, setNodes] = useState<NodeExecution[]>([]);
  const [selectedNodeIndex, setSelectedNodeIndex] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load workflow data when modal opens
  useEffect(() => {
    if (isOpen && executionId) {
      loadWorkflowData();
    } else {
      // Reset state when modal closes
      setWorkflow(null);
      setNodes([]);
      setSelectedNodeIndex(0);
      setError(null);
    }
  }, [isOpen, executionId]);

  const loadWorkflowData = async () => {
    if (!executionId) return;

    setIsLoading(true);
    setError(null);

    try {
      const [workflowData, nodeData] = await Promise.all([
        fetchWorkflowExecution(executionId),
        fetchNodeExecutions(executionId),
      ]);

      setWorkflow(workflowData);
      setNodes(nodeData);
      setSelectedNodeIndex(0); // Start at first node
    } catch (err) {
      console.error("Failed to load workflow data:", err);
      setError(err instanceof Error ? err.message : "Failed to load workflow");
    } finally {
      setIsLoading(false);
    }
  };

  const handleNodeClick = (nodeIndex: number) => {
    setSelectedNodeIndex(nodeIndex);
  };

  const handleTimelineChange = (nodeIndex: number) => {
    setSelectedNodeIndex(nodeIndex);
  };

  const handlePrevNode = () => {
    if (selectedNodeIndex > 0) {
      setSelectedNodeIndex(selectedNodeIndex - 1);
    }
  };

  const handleNextNode = () => {
    if (selectedNodeIndex < nodes.length - 1) {
      setSelectedNodeIndex(selectedNodeIndex + 1);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop overlay */}
      <div className="workflow-modal-backdrop" onClick={onClose} />

      {/* Modal content - slides in from left */}
      <div className={`workflow-modal ${isOpen ? "open" : ""}`}>
        <div className="workflow-modal-header">
          <h2>🔍 Workflow Debugger</h2>
          <button className="close-button" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="workflow-modal-body">
          {isLoading && (
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading workflow data...</p>
            </div>
          )}

          {error && (
            <div className="error-state">
              <p>❌ {error}</p>
              <button onClick={loadWorkflowData}>Retry</button>
            </div>
          )}

          {!isLoading && !error && nodes.length === 0 && (
            <div className="empty-state">
              <p>No workflow data available for this message.</p>
              <p className="hint">This might be an old message from before tracking was enabled.</p>
            </div>
          )}

          {!isLoading && !error && nodes.length > 0 && (
            <>
              {/* Top section: Workflow metadata */}
              {workflow && (
                <div className="workflow-metadata">
                  <div className="metadata-item">
                    <span className="label">Query:</span>
                    <span className="value">{workflow.query}</span>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-item">
                      <span className="label">Duration:</span>
                      <span className="value">{workflow.duration_ms.toFixed(0)}ms</span>
                    </div>
                    <div className="metadata-item">
                      <span className="label">Nodes:</span>
                      <span className="value">{nodes.length}</span>
                    </div>
                    <div className="metadata-item">
                      <span className="label">Status:</span>
                      <span className={`status-badge ${workflow.status}`}>
                        {workflow.status}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Middle section: Graph + Details Panel */}
              <div className="workflow-content">
                <div className="graph-section">
                  <WorkflowGraph
                    nodes={nodes}
                    selectedNodeIndex={selectedNodeIndex}
                    onNodeClick={handleNodeClick}
                  />
                </div>

                <div className="details-section">
                  <NodeDetailsPanel node={nodes[selectedNodeIndex]} />
                </div>
              </div>

              {/* Bottom section: Timeline navigation */}
              <div className="timeline-section">
                <WorkflowTimeline
                  nodes={nodes}
                  selectedNodeIndex={selectedNodeIndex}
                  onNodeSelect={handleTimelineChange}
                  onPrev={handlePrevNode}
                  onNext={handleNextNode}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
