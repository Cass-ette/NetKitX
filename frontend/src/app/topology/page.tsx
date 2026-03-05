"use client";

import { useEffect, useState, useTransition } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TopologyGraph } from "@/components/topology/topology-graph";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

interface Task {
  id: number;
  plugin_name: string;
  status: string;
  created_at: string;
}

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

export default function TopologyPage() {
  const token = useAuth((s) => s.token);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [topology, setTopology] = useState<TopologyData | null>(null);
  const [isPending, startTransition] = useTransition();

  // Fetch completed tasks
  useEffect(() => {
    if (!token) return;
    api<Task[]>("/api/v1/tasks?status=done", { token }).then((data) => {
      setTasks(data);
      if (data.length > 0) {
        setSelectedTaskId(String(data[0].id));
      }
    });
  }, [token]);

  // Fetch topology for selected task
  useEffect(() => {
    if (!selectedTaskId || !token) return;
    startTransition(async () => {
      try {
        const data = await api<TopologyData>(
          `/api/v1/topology/tasks/${selectedTaskId}`,
          { token },
        );
        setTopology(data);
      } catch {
        setTopology(null);
      }
    });
  }, [selectedTaskId, token]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Network Topology</h1>
        <p className="text-muted-foreground">
          Visualize scan results as a network graph
        </p>
      </div>

      <div className="flex items-center gap-4">
        <Select
          value={selectedTaskId || undefined}
          onValueChange={setSelectedTaskId}
        >
          <SelectTrigger className="w-[400px]">
            <SelectValue placeholder="Select a completed task" />
          </SelectTrigger>
          <SelectContent>
            {tasks.map((task) => (
              <SelectItem key={task.id} value={String(task.id)}>
                #{task.id} — {task.plugin_name} ({new Date(task.created_at).toLocaleDateString()})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {topology && (
          <div className="flex gap-2">
            <Badge variant="outline">
              {topology.nodes.filter((n) => n.type === "host").length} hosts
            </Badge>
            <Badge variant="outline">
              {topology.edges.length} connections
            </Badge>
          </div>
        )}
      </div>

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Topology Graph</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="h-[600px]">
            {isPending ? (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                Loading topology...
              </div>
            ) : topology && topology.nodes.length > 0 ? (
              <TopologyGraph data={topology} />
            ) : (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                {tasks.length === 0
                  ? "No completed tasks found. Run a scan first."
                  : "No topology data for this task."}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
