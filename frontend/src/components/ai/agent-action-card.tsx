"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Play, SkipForward, CheckCircle, Terminal, Plug, ExternalLink } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import Link from "next/link";
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

  return (
    <Card className="border-primary/30 bg-primary/5 w-full max-w-[80%]">
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
              <p className="text-destructive">{result.error}</p>
            ) : (result.exit_code != null && result.exit_code !== 0) ? (
              <div className="space-y-1">
                <p className="text-destructive">Exit: {result.exit_code}</p>
                {result.stderr && (
                  <pre className="font-mono text-destructive/80 bg-muted rounded p-1.5 max-h-24 overflow-y-auto whitespace-pre-wrap">
                    {result.stderr.slice(0, 500)}
                  </pre>
                )}
              </div>
            ) : (
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle className="h-3 w-3" />
                  <span>
                    {result.items
                      ? `${result.items.length} result(s)`
                      : result.stdout
                        ? `Exit: 0`
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
                {result.stdout && (
                  <pre className="font-mono text-muted-foreground bg-muted rounded p-1.5 max-h-24 overflow-y-auto whitespace-pre-wrap">
                    {result.stdout.slice(0, 500)}{result.stdout.length > 500 ? "…" : ""}
                  </pre>
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
