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
import { useTranslations } from "@/i18n/use-translations";

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
  const { t, locale } = useTranslations("topology");
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
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground">
          {t("subtitle")}
        </p>
      </div>

      <div className="flex items-center gap-4">
        <Select
          value={selectedTaskId || undefined}
          onValueChange={setSelectedTaskId}
        >
          <SelectTrigger className="w-[400px]">
            <SelectValue placeholder={t("selectCompletedTask")} />
          </SelectTrigger>
          <SelectContent>
            {tasks.map((task) => (
              <SelectItem key={task.id} value={String(task.id)}>
                #{task.id} — {task.plugin_name} ({new Date(task.created_at).toLocaleDateString(locale)})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {topology && (
          <div className="flex gap-2">
            <Badge variant="outline">
              {t("hosts", { count: topology.nodes.filter((n) => n.type === "host").length })}
            </Badge>
            <Badge variant="outline">
              {t("connections", { count: topology.edges.length })}
            </Badge>
          </div>
        )}
      </div>

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>{t("topologyGraph")}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="h-[600px]">
            {isPending ? (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                {t("loadingTopology")}
              </div>
            ) : topology && topology.nodes.length > 0 ? (
              <TopologyGraph data={topology} />
            ) : (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                {tasks.length === 0
                  ? t("noCompletedTasks")
                  : t("noTopologyData")}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
