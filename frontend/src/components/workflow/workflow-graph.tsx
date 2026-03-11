"use client";

import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeTypes,
  type NodeMouseHandler,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import {
  WorkflowStartNode,
  WorkflowEndNode,
  WorkflowPluginNode,
  WorkflowShellNode,
} from "./workflow-nodes";
import type { WorkflowNode, WorkflowEdge } from "@/types";
import "@xyflow/react/dist/style.css";

const nodeTypes: NodeTypes = {
  start: WorkflowStartNode,
  end: WorkflowEndNode,
  "action-plugin": WorkflowPluginNode,
  "action-shell": WorkflowShellNode,
};

interface WorkflowGraphProps {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  nodeStatuses?: Record<string, string>;
  selectedNodeId?: string | null;
  nodeSummaries?: Record<string, string>;
  onNodeClick?: (nodeId: string) => void;
}

function layoutGraph(
  wfNodes: WorkflowNode[],
  wfEdges: WorkflowEdge[],
  nodeStatuses?: Record<string, string>,
  selectedNodeId?: string | null,
  nodeSummaries?: Record<string, string>,
) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", ranksep: 80, nodesep: 50 });

  for (const node of wfNodes) {
    const isTerminal = node.type === "start" || node.type === "end";
    const width = isTerminal ? 60 : 220;
    const height = isTerminal ? 60 : 90;
    g.setNode(node.id, { width, height });
  }

  for (const edge of wfEdges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const nodes: Node[] = wfNodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id,
      type: n.type,
      position: { x: pos.x - pos.width / 2, y: pos.y - pos.height / 2 },
      data: {
        ...n.data,
        label: n.label,
        status: nodeStatuses?.[n.id] || "pending",
        selected: n.id === selectedNodeId,
        liveSummary: nodeSummaries?.[n.id],
      },
    };
  });

  const edges: Edge[] = wfEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: true,
    style: { stroke: "hsl(var(--primary))" },
  }));

  return { nodes, edges };
}

export function WorkflowGraph({
  nodes: wfNodes,
  edges: wfEdges,
  nodeStatuses,
  selectedNodeId,
  nodeSummaries,
  onNodeClick,
}: WorkflowGraphProps) {
  const layout = useMemo(
    () => layoutGraph(wfNodes, wfEdges, nodeStatuses, selectedNodeId, nodeSummaries),
    [wfNodes, wfEdges, nodeStatuses, selectedNodeId, nodeSummaries],
  );

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      onNodeClick?.(node.id);
    },
    [onNodeClick],
  );

  return (
    <div className="h-full w-full">
      <ReactFlow
        key={JSON.stringify(nodeStatuses) + selectedNodeId}
        nodes={layout.nodes}
        edges={layout.edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
