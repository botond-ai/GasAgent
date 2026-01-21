import { NodeExecution } from "../../types";
import "./NodeDetailsPanel.css";

interface NodeDetailsPanelProps {
  node: NodeExecution | null;
}

/**
 * Node Details Panel - Displays node input/output state
 * 
 * Shows JSON formatted state_before and state_after with collapsible sections.
 * Helps debug workflow execution by inspecting node transformations.
 */
export function NodeDetailsPanel({ node }: NodeDetailsPanelProps) {
  if (!node) {
    return (
      <div className="node-details-panel">
        <div className="empty-state">
          <p>No node selected</p>
        </div>
      </div>
    );
  }

  const renderJSON = (data: any, label: string) => {
    if (!data) {
      return (
        <div className="json-section">
          <h4>{label}</h4>
          <div className="json-empty">No data</div>
        </div>
      );
    }

    // Remove large arrays/objects for better readability
    const simplified = simplifyData(data);

    return (
      <div className="json-section">
        <h4>{label}</h4>
        <pre className="json-content">
          {JSON.stringify(simplified, null, 2)}
        </pre>
      </div>
    );
  };

  const simplifyData = (data: any): any => {
    if (Array.isArray(data)) {
      if (data.length > 5) {
        return [`... ${data.length} items ...`];
      }
      return data.map(simplifyData);
    }

    if (typeof data === "object" && data !== null) {
      const simplified: any = {};
      const keys = Object.keys(data);

      for (const key of keys) {
        const value = data[key];

        // Truncate long strings
        if (typeof value === "string" && value.length > 200) {
          simplified[key] = value.substring(0, 200) + "...";
        }
        // Truncate large arrays
        else if (Array.isArray(value) && value.length > 5) {
          simplified[key] = [`... ${value.length} items ...`];
        }
        // Recursively simplify nested objects
        else if (typeof value === "object" && value !== null) {
          simplified[key] = simplifyData(value);
        }
        // Keep primitive values
        else {
          simplified[key] = value;
        }
      }

      return simplified;
    }

    return data;
  };

  return (
    <div className="node-details-panel">
      <div className="node-header-info">
        <h3>{node.node_name}</h3>
        <div className="node-meta">
          <span className={`status-badge ${node.status}`}>
            {node.status}
          </span>
          <span className="duration-badge">
            {node.duration_ms.toFixed(0)}ms
          </span>
        </div>
      </div>

      {node.error_message && (
        <div className="error-message">
          <strong>Error:</strong> {node.error_message}
        </div>
      )}

      <div className="node-states">
        {renderJSON(node.metadata, "Metadata")}
        {renderJSON(node.state_before, "Input State")}
        {renderJSON(node.state_after, "Output State")}
      </div>
    </div>
  );
}
