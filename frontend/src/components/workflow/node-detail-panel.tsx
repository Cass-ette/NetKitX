"use client";

import { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, ChevronDown, ChevronRight, Bot } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { WorkflowNode } from "@/types";

interface NodeDetailPanelProps {
  node: WorkflowNode | null;
  onClose: () => void;
  currentStep: { step: number; total: number } | null;
  nodeStatus?: string;
  result?: unknown;
  resultSummary?: string;
  reflection?: string;
  reflectionLoading?: boolean;
  hasAI?: boolean;
}

export function NodeDetailPanel({
  node,
  onClose,
  currentStep,
  nodeStatus,
  result,
  resultSummary,
  reflection,
  reflectionLoading,
  hasAI,
}: NodeDetailPanelProps) {
  const { t } = useTranslations("workflows");
  const [resultExpanded, setResultExpanded] = useState(false);

  if (!node) return null;

  const isTerminal = node.type === "start" || node.type === "end";
  const params = node.data?.params;
  const reason = node.data?.reason;
  const displaySummary = resultSummary || node.data?.result_summary;
  const status = nodeStatus || "pending";

  return (
    <Sheet open={!!node} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <span className="truncate">{node.label}</span>
            <Badge
              variant={
                status === "done"
                  ? "default"
                  : status === "failed"
                    ? "destructive"
                    : status === "running"
                      ? "secondary"
                      : "outline"
              }
            >
              {status}
            </Badge>
          </SheetTitle>
          {currentStep && (
            <p className="text-sm text-muted-foreground">
              {t("stepProgress", {
                step: currentStep.step,
                total: currentStep.total,
              })}
            </p>
          )}
        </SheetHeader>

        {isTerminal ? (
          <div className="mt-6">
            <p className="text-sm text-muted-foreground">
              {node.type === "start" ? "Workflow start" : "Workflow end"}
            </p>
          </div>
        ) : (
          <div className="mt-6 space-y-4">
            {/* Parameters */}
            {params && Object.keys(params).length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1">
                  {t("params")}
                </h4>
                <div className="rounded-md bg-muted p-2 text-xs font-mono space-y-0.5">
                  {Object.entries(params).map(([k, v]) => (
                    <div key={k}>
                      <span className="text-primary">{k}</span>: {String(v)}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Reason */}
            {reason && (
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1">
                  {t("reason")}
                </h4>
                <p className="text-sm">{reason}</p>
              </div>
            )}

            {/* Result */}
            {(result || displaySummary) && (
              <div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full justify-start px-0 hover:bg-transparent"
                  onClick={() => setResultExpanded(!resultExpanded)}
                >
                  {resultExpanded ? (
                    <ChevronDown className="h-4 w-4 mr-1" />
                  ) : (
                    <ChevronRight className="h-4 w-4 mr-1" />
                  )}
                  <span className="text-sm font-medium text-muted-foreground">
                    {t("result")}
                  </span>
                  {displaySummary && (
                    <span className="ml-2 text-xs text-muted-foreground/70">
                      {displaySummary}
                    </span>
                  )}
                </Button>
                {resultExpanded && result != null && (
                  <pre className="mt-1 max-h-60 overflow-auto rounded-md bg-muted p-2 text-xs font-mono whitespace-pre-wrap break-all">
                    {typeof result === "string"
                      ? result
                      : JSON.stringify(result, null, 2)}
                  </pre>
                )}
              </div>
            )}

            {/* AI Reflection */}
            {hasAI !== false && (
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1 flex items-center gap-1.5">
                  <Bot className="h-4 w-4" />
                  {t("reflection")}
                </h4>
                {reflectionLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    {t("reflectionLoading")}
                  </div>
                ) : reflection ? (
                  <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {reflection}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground/70">
                    {t("noReflection")}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
