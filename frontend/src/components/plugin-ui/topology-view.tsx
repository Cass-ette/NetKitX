"use client";

import { useEffect, useState, useTransition } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TopologyGraph } from "@/components/topology/topology-graph";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTranslations } from "@/i18n/use-translations";
import type { PluginUIProps } from "@/types";

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

export default function TopologyView({ taskId, taskStatus }: PluginUIProps) {
  const token = useAuth((s) => s.token);
  const { t } = useTranslations("topology");
  const [data, setData] = useState<TopologyData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!taskId || taskStatus !== "done" || !token) return;

    startTransition(async () => {
      try {
        const result = await api<TopologyData>(`/api/v1/topology/tasks/${taskId}`, { token });
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load topology");
      }
    });
  }, [taskId, taskStatus, token]);

  if (isPending) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-96 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.nodes.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[500px]">
          <TopologyGraph data={data} />
        </div>
      </CardContent>
    </Card>
  );
}
