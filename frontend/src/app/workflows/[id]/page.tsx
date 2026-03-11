"use client";

import { useEffect, useState, useTransition, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useTranslations } from "@/i18n/use-translations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowLeft, Play, Loader2 } from "lucide-react";
import { WorkflowGraph } from "@/components/workflow/workflow-graph";
import type { Workflow } from "@/types";

export default function WorkflowDetailPage() {
  const { t } = useTranslations("workflows");
  const token = useAuth((s) => s.token);
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;

  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [isPending, startTransition] = useTransition();
  const [isRunning, setIsRunning] = useState(false);
  const [nodeStatuses, setNodeStatuses] = useState<Record<string, string>>({});
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!token || !workflowId) return;
    startTransition(async () => {
      try {
        const data = await api<Workflow>(
          `/api/v1/workflows/${workflowId}`,
          { token },
        );
        setWorkflow(data);
      } catch (err) {
        console.error("Failed to fetch workflow:", err);
      }
    });
  }, [token, workflowId]);

  const handleRun = useCallback(async () => {
    if (!token || !workflowId || isRunning) return;
    setIsRunning(true);
    setNodeStatuses({});

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const resp = await fetch(
        `${apiUrl}/api/v1/workflows/${workflowId}/run`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          signal: controller.signal,
        },
      );

      if (!resp.ok || !resp.body) {
        setIsRunning(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(line.slice(6));
            const event = payload.event as string;

            if (event === "node_start") {
              setNodeStatuses((prev) => ({
                ...prev,
                [payload.node_id]: "running",
              }));
            } else if (event === "node_result") {
              setNodeStatuses((prev) => ({
                ...prev,
                [payload.node_id]: "done",
              }));
            } else if (event === "node_error") {
              setNodeStatuses((prev) => ({
                ...prev,
                [payload.node_id]: "failed",
              }));
            } else if (event === "workflow_done") {
              setIsRunning(false);
            }
          } catch {
            // skip malformed
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        console.error("Workflow run error:", err);
      }
    } finally {
      setIsRunning(false);
      abortRef.current = null;
    }
  }, [token, workflowId, isRunning]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  if (isPending || !workflow) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">{t("loading")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push("/workflows")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold truncate">{workflow.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline">
              {t("nodeCount", { count: workflow.nodes.length })}
            </Badge>
            {workflow.session_id && (
              <Badge variant="secondary">Session #{workflow.session_id}</Badge>
            )}
            <span className="text-sm text-muted-foreground">
              {new Date(workflow.created_at).toLocaleString()}
            </span>
          </div>
        </div>
        <Button
          onClick={handleRun}
          disabled={isRunning}
          size="sm"
        >
          {isRunning ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              {t("running")}
            </>
          ) : (
            <>
              <Play className="h-4 w-4 mr-2" />
              {t("runWorkflow")}
            </>
          )}
        </Button>
      </div>

      {/* Graph */}
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div className="h-[600px]">
            <WorkflowGraph
              nodes={workflow.nodes}
              edges={workflow.edges}
              nodeStatuses={nodeStatuses}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
