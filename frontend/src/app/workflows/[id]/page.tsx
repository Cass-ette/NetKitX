"use client";

import { useEffect, useState, useTransition, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useTranslations } from "@/i18n/use-translations";
import { useLocaleStore } from "@/i18n/store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowLeft, Play, Loader2, Eye } from "lucide-react";
import { WorkflowGraph } from "@/components/workflow/workflow-graph";
import { NodeDetailPanel } from "@/components/workflow/node-detail-panel";
import type { Workflow } from "@/types";

export default function WorkflowDetailPage() {
  const { t } = useTranslations("workflows");
  const token = useAuth((s) => s.token);
  const locale = useLocaleStore((s) => s.locale);
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;

  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [isPending, startTransition] = useTransition();
  const [isRunning, setIsRunning] = useState(false);
  const [nodeStatuses, setNodeStatuses] = useState<Record<string, string>>({});
  const [nodeResults, setNodeResults] = useState<Record<string, unknown>>({});
  const [nodeReflections, setNodeReflections] = useState<Record<string, string>>({});
  const [nodeSummaries, setNodeSummaries] = useState<Record<string, string>>({});
  const [reflectionLoading, setReflectionLoading] = useState<Record<string, boolean>>({});
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<{ step: number; total: number } | null>(null);
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

  const [isSimulating, setIsSimulating] = useState(false);

  const handleRun = useCallback(async (simulate = false) => {
    if (!token || !workflowId || isRunning) return;
    setIsRunning(true);
    setIsSimulating(simulate);
    setNodeStatuses({});
    setNodeResults({});
    setNodeReflections({});
    setNodeSummaries({});
    setReflectionLoading({});
    setCurrentStep(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const resp = await fetch(
        `${apiUrl}/api/v1/workflows/${workflowId}/run?reflect=true&lang=${locale}&simulate=${simulate}`,
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
              const nodeId = payload.node_id as string;
              setNodeStatuses((prev) => ({ ...prev, [nodeId]: "running" }));
              setCurrentStep({ step: payload.step, total: payload.total_steps });
              setSelectedNodeId(nodeId);
              setReflectionLoading((prev) => ({ ...prev, [nodeId]: true }));
            } else if (event === "node_result") {
              const nodeId = payload.node_id as string;
              const isNodeSimulated = !!(payload.result as Record<string, unknown>)?.simulated;
              setNodeStatuses((prev) => ({ ...prev, [nodeId]: isNodeSimulated ? "simulated" : "done" }));
              setNodeResults((prev) => ({ ...prev, [nodeId]: payload.result }));
              if (payload.result_summary) {
                setNodeSummaries((prev) => ({ ...prev, [nodeId]: payload.result_summary }));
              }
            } else if (event === "node_reflection") {
              const nodeId = payload.node_id as string;
              setNodeReflections((prev) => ({ ...prev, [nodeId]: payload.reflection }));
              setReflectionLoading((prev) => ({ ...prev, [nodeId]: false }));
            } else if (event === "node_skip") {
              const nodeId = payload.node_id as string;
              setNodeStatuses((prev) => ({ ...prev, [nodeId]: "skipped" }));
            } else if (event === "node_error") {
              const nodeId = payload.node_id as string;
              setNodeStatuses((prev) => ({ ...prev, [nodeId]: "failed" }));
              setReflectionLoading((prev) => ({ ...prev, [nodeId]: false }));
            } else if (event === "workflow_done") {
              setIsRunning(false);
              // Clear remaining loading states
              setReflectionLoading({});
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
      setIsSimulating(false);
      abortRef.current = null;
    }
  }, [token, workflowId, isRunning, locale]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleNodeClick = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
  }, []);

  const selectedNode = workflow?.nodes.find((n) => n.id === selectedNodeId) ?? null;

  // Find step info for selected node
  const selectedStepInfo = (() => {
    if (!selectedNodeId || !workflow) return null;
    const actionNodes = workflow.nodes.filter(
      (n) => n.type !== "start" && n.type !== "end",
    );
    const idx = actionNodes.findIndex((n) => n.id === selectedNodeId);
    if (idx === -1) return null;
    return { step: idx + 1, total: actionNodes.length };
  })();

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
          variant="outline"
          onClick={() => handleRun(true)}
          disabled={isRunning}
          size="sm"
        >
          {isRunning && isSimulating ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              {t("simulating")}
            </>
          ) : (
            <>
              <Eye className="h-4 w-4 mr-2" />
              {t("simulate")}
            </>
          )}
        </Button>
        <Button
          onClick={() => handleRun(false)}
          disabled={isRunning}
          size="sm"
        >
          {isRunning && !isSimulating ? (
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

      {/* Step progress */}
      {currentStep && isRunning && (
        <div className="text-sm text-muted-foreground">
          {t("stepProgress", { step: currentStep.step, total: currentStep.total })}
        </div>
      )}

      {/* Graph */}
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div className="h-[600px]">
            <WorkflowGraph
              nodes={workflow.nodes}
              edges={workflow.edges}
              nodeStatuses={nodeStatuses}
              selectedNodeId={selectedNodeId}
              nodeSummaries={nodeSummaries}
              onNodeClick={handleNodeClick}
            />
          </div>
        </CardContent>
      </Card>

      {/* Node Detail Panel */}
      <NodeDetailPanel
        node={selectedNode}
        onClose={() => setSelectedNodeId(null)}
        currentStep={selectedStepInfo}
        nodeStatus={selectedNodeId ? nodeStatuses[selectedNodeId] : undefined}
        result={selectedNodeId ? nodeResults[selectedNodeId] : undefined}
        resultSummary={selectedNodeId ? nodeSummaries[selectedNodeId] : undefined}
        reflection={selectedNodeId ? nodeReflections[selectedNodeId] : undefined}
        reflectionLoading={selectedNodeId ? reflectionLoading[selectedNodeId] : false}
      />
    </div>
  );
}
