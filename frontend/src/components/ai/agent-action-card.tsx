"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Play, SkipForward, CheckCircle, Terminal, Plug, ExternalLink } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import Link from "next/link";
import { AgentOutputBlock } from "@/components/ai/agent-output-block";
import type { AgentAction, AgentActionResult } from "@/types";

interface AgentActionCardProps {
  action: AgentAction;
  status: "proposed" | "executing" | "done" | "skipped";
  result?: AgentActionResult;
  taskId?: number;
  onConfirm?: (approved: boolean) => void;
}

export function AgentActionCard({
  action,
  status,
  result,
  taskId,
  onConfirm,
}: AgentActionCardProps) {
  const { t } = useTranslations("ai");
  const logsOutput = result?.logs?.join("\n");
  const itemsOutput = result?.items?.length ? JSON.stringify(result.items, null, 2) : "";

  return (
    <Card className="w-full border-primary/30 bg-primary/5">
      <CardContent className="p-3 space-y-2">
        {/* Header */}
        <div className="flex items-center gap-2">
          {action.type === "plugin" ? (
            <Plug className="h-4 w-4 text-primary" />
          ) : (
            <Terminal className="h-4 w-4 text-orange-500" />
          )}
          <span className="font-semibold text-sm">
            {action.type === "plugin"
              ? `Plugin: ${action.plugin}`
              : `Shell: ${(action.command ?? "").slice(0, 60)}${(action.command ?? "").length > 60 ? "…" : ""}`}
          </span>
          <Badge
            variant={status === "done" ? "default" : status === "skipped" ? "secondary" : "outline"}
            className="ml-auto text-xs"
          >
            {status === "proposed" && t("actionProposed")}
            {status === "executing" && t("agentExecuting")}
            {status === "done" && t("agentDone")}
            {status === "skipped" && t("actionSkip")}
          </Badge>
        </div>

        {/* Plugin params */}
        {action.type === "plugin" && action.params && Object.keys(action.params).length > 0 && (
          <div className="text-xs font-mono bg-muted rounded p-2 space-y-0.5">
            {Object.entries(action.params).map(([k, v]) => (
              <div key={k}>
                <span className="text-muted-foreground">{k}: </span>
                <span>{v}</span>
              </div>
            ))}
          </div>
        )}

        {/* Shell command */}
        {action.type === "shell" && action.command && (
          <div className="text-xs font-mono bg-muted rounded p-2">
            $ {action.command}
          </div>
        )}

        {/* Reason */}
        {action.reason && (
          <p className="text-xs text-muted-foreground italic">{action.reason}</p>
        )}

        {/* Executing spinner */}
        {status === "executing" && (
          <div className="flex items-center gap-2 text-muted-foreground text-xs">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>{t("agentExecuting")}…</span>
            {taskId && <span className="opacity-50">#{taskId}</span>}
          </div>
        )}

        {/* Result summary */}
        {status === "done" && result && (
          <div className="text-xs space-y-1">
            {result.error ? (
              <AgentOutputBlock
                title={t("actionErrorOutput")}
                content={result.error}
                tone="error"
              />
            ) : (result.exit_code != null && result.exit_code !== 0) ? (
              <div className="space-y-1">
                <p className="text-destructive">{t("actionExitCode", { code: result.exit_code })}</p>
                {result.stderr && (
                  <AgentOutputBlock
                    title={t("actionErrorOutput")}
                    content={result.stderr}
                    tone="error"
                  />
                )}
                {result.stdout && (
                  <AgentOutputBlock title={t("actionOutput")} content={result.stdout} />
                )}
              </div>
            ) : (
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle className="h-3 w-3" />
                  <span>
                    {result.items
                      ? t("actionResultCount", { count: result.items.length })
                      : result.stdout
                        ? t("actionExitCode", { code: 0 })
                        : t("agentDone")}
                  </span>
                  {taskId && (
                    <Link
                      href={`/tasks/${taskId}`}
                      className="ml-auto underline flex items-center gap-1 text-primary"
                    >
                      <ExternalLink className="h-3 w-3" />
                      {t("viewTask")}
                    </Link>
                  )}
                </div>
                {logsOutput && (
                  <AgentOutputBlock title={t("actionLogs")} content={logsOutput} />
                )}
                {result.stdout && (
                  <AgentOutputBlock title={t("actionOutput")} content={result.stdout} />
                )}
                {result.stderr && (
                  <AgentOutputBlock
                    title={t("actionErrorOutput")}
                    content={result.stderr}
                    tone="error"
                  />
                )}
                {itemsOutput && (
                  <AgentOutputBlock title={t("actionResults")} content={itemsOutput} />
                )}
              </div>
            )}
          </div>
        )}

        {/* Confirm buttons (Mode A) */}
        {status === "proposed" && onConfirm && (
          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              variant="default"
              className="h-7 text-xs"
              onClick={() => onConfirm(true)}
            >
              <Play className="h-3 w-3 mr-1" />
              {t("actionExecute")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => onConfirm(false)}
            >
              <SkipForward className="h-3 w-3 mr-1" />
              {t("actionSkip")}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
