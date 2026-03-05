"use client";

import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeTypes,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import { HostNode } from "./host-node";
import { ScannerNode } from "./scanner-node";
import { NodeDetailPanel } from "./node-detail-panel";
import "@xyflow/react/dist/style.css";

interface TopologyData {
  nodes: Array<{
    id: string;
    type: string;
    label: string;
    data: Record<string, unknown>;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
  }>;
}

const nodeTypes: NodeTypes = {
  host: HostNode,
  scanner: ScannerNode,
};

function layoutGraph(data: TopologyData) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", ranksep: 80, nodesep: 40 });

  for (const node of data.nodes) {
    const width = node.type === "scanner" ? 150 : 180;
    const height = node.type === "scanner" ? 100 : 80;
    g.setNode(node.id, { width, height });
  }

  for (const edge of data.edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const nodes: Node[] = data.nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id,
      type: n.type,
      position: { x: pos.x - pos.width / 2, y: pos.y - pos.height / 2 },
      data: { label: n.label, ...n.data },
    };
  });

  const edges: Edge[] = data.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: true,
    style: { stroke: "hsl(var(--primary))" },
  }));

  return { nodes, edges };
}

interface TopologyGraphProps {
  data: TopologyData;
}

export function TopologyGraph({ data }: TopologyGraphProps) {
  const layout = useMemo(() => layoutGraph(data), [data]);
  const [nodes, , onNodesChange] = useNodesState(layout.nodes);
  const [edges, , onEdgesChange] = useEdgesState(layout.edges);
  const [selectedNode, setSelectedNode] = useState<TopologyData["nodes"][number] | null>(null);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const original = data.nodes.find((n) => n.id === node.id);
      if (original) setSelectedNode(original);
    },
    [data.nodes],
  );

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
      </ReactFlow>
      <NodeDetailPanel
        node={selectedNode}
        onClose={() => setSelectedNode(null)}
      />
    </div>
  );
}
