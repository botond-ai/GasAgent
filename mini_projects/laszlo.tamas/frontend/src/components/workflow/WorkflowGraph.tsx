import { useMemo } from "react";
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  NodeTypes,
} from "reactflow";
import "reactflow/dist/style.css";
import { NodeExecution } from "../../types";
import { WorkflowNode } from "./WorkflowNode";
import "./WorkflowGraph.css";

interface WorkflowGraphProps {
  nodes: NodeExecution[];
  selectedNodeIndex: number;
  onNodeClick: (nodeIndex: number) => void;
}

const nodeTypes: NodeTypes = {
  workflow: WorkflowNode,
};

/**
 * Workflow Graph - React Flow visualization
 * 
 * Renders workflow execution as a directed graph with nodes and edges.
 * Highlights selected node, shows execution status (success/error).
 * 
 * Supports hierarchical nodes: child nodes (with parent_node set) are rendered
 * horizontally next to their parent for visual grouping.
 */
export function WorkflowGraph({
  nodes,
  selectedNodeIndex,
  onNodeClick,
}: WorkflowGraphProps) {
  // Convert NodeExecution[] to React Flow nodes with hierarchy support
  const flowNodes: Node[] = useMemo(() => {
    const result: Node[] = [];
    let yOffset = 0;
    const processedIndices = new Set<number>();
    
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      const isChild = node.parent_node != null;
      
      // Skip if already processed as a child
      if (processedIndices.has(i)) {
        continue;
      }
      
      // Skip child nodes in main loop - they'll be rendered with their parent
      if (isChild) {
        continue;
      }
      
      // Main node - use left side
      const mainNodeX = 150;
      result.push({
        id: `node-${i}`,
        type: "workflow",
        position: { x: mainNodeX, y: yOffset },
        data: {
          nodeName: node.node_name,
          duration: node.duration_ms,
          status: node.status,
          isSelected: i === selectedNodeIndex,
          onClick: () => onNodeClick(i),
        },
      });
      
      // Find child nodes (nodes with parent_node === current node_name)
      const children = nodes
        .map((n, idx) => ({ node: n, index: idx }))
        .filter(({ node: n }) => n.parent_node === node.node_name);
      
      if (children.length > 0) {
        // Render children horizontally next to parent (same Y position)
        children.forEach(({ node: childNode, index: childIdx }, childOffset) => {
          result.push({
            id: `node-${childIdx}`,
            type: "workflow",
            position: { x: 400 + childOffset * 220, y: yOffset }, // Same Y as parent!
            data: {
              nodeName: childNode.node_name,
              duration: childNode.duration_ms,
              status: childNode.status,
              isSelected: childIdx === selectedNodeIndex,
              onClick: () => onNodeClick(childIdx),
            },
          });
          processedIndices.add(childIdx);
        });
      }
      
      // Only increment Y for main nodes (not for each child)
      yOffset += 120;
    }
    
    return result;
  }, [nodes, selectedNodeIndex, onNodeClick]);

  // Create edges: main flow + parent-child connections
  const flowEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [];
    let prevMainNodeIndex = -1;
    
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      const isChild = node.parent_node != null;
      
      if (isChild) {
        // Child node: connect to parent
        const parentIndex = nodes.findIndex((n) => n.node_name === node.parent_node);
        if (parentIndex >= 0) {
          edges.push({
            id: `edge-parent-${parentIndex}-child-${i}`,
            source: `node-${parentIndex}`,
            target: `node-${i}`,
            type: "smoothstep",
            animated: parentIndex === selectedNodeIndex || i === selectedNodeIndex,
            style: {
              stroke: i <= selectedNodeIndex ? "#22c55e" : "#475569",
              strokeWidth: 2,
            },
          });
        }
      } else {
        // Main node: connect to previous main node
        if (prevMainNodeIndex >= 0) {
          edges.push({
            id: `edge-${prevMainNodeIndex}-${i}`,
            source: `node-${prevMainNodeIndex}`,
            target: `node-${i}`,
            type: "smoothstep",
            animated: prevMainNodeIndex === selectedNodeIndex || i === selectedNodeIndex,
            style: {
              stroke: i <= selectedNodeIndex ? "#22c55e" : "#475569",
              strokeWidth: 2,
            },
          });
        }
        prevMainNodeIndex = i;
      }
    }
    
    return edges;
  }, [nodes, selectedNodeIndex]);

  return (
    <div className="workflow-graph-container">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.5}
        maxZoom={1.5}
        defaultEdgeOptions={{
          type: "smoothstep",
        }}
      >
        <Background />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            if (node.data.status === "error") return "#ef4444";
            if (node.data.status === "success") return "#22c55e";
            return "#94a3b8";
          }}
          maskColor="rgba(0, 0, 0, 0.5)"
        />
      </ReactFlow>
    </div>
  );
}
