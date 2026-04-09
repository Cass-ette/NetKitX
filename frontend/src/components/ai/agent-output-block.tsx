"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, TerminalSquare } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import { cn } from "@/lib/utils";

interface AgentOutputBlockProps {
  title: string;
  content?: string | null;
  tone?: "default" | "error";
  className?: string;
}

export function AgentOutputBlock({
  title,
  content,
  tone = "default",
  className,
}: AgentOutputBlockProps) {
  const { t } = useTranslations("ai");
  const normalized = content?.trim() ?? "";
  const lineCount = normalized ? normalized.split(/\r?\n/).length : 0;
  const expandable = normalized.length > 280 || lineCount > 8;
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border",
        tone === "error"
          ? "border-red-500/30 bg-red-950/10"
          : "border-zinc-800/80 bg-zinc-950 text-zinc-50",
        className,
      )}
    >
      <div
        className={cn(
          "flex items-center gap-2 border-b px-3 py-2",
          tone === "error"
            ? "border-red-500/20 bg-red-950/20 text-red-200"
            : "border-zinc-800/80 bg-zinc-900/80 text-zinc-300",
        )}
      >
        {tone === "error" ? (
          <AlertTriangle className="h-3.5 w-3.5" />
        ) : (
          <TerminalSquare className="h-3.5 w-3.5" />
        )}
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em]">
          {title}
        </span>
        {lineCount > 0 && (
          <span className="ml-auto text-[10px] text-current/70">
            {t("actionLineCount", { count: lineCount })}
          </span>
        )}
      </div>

      <div className="relative">
        <pre
          className={cn(
            "m-0 whitespace-pre-wrap break-all px-3 py-3 text-xs leading-5 font-mono",
            tone === "error" ? "text-red-100" : "text-zinc-100",
            !expanded && expandable && "max-h-40 overflow-hidden",
          )}
        >
          {normalized || t("actionEmptyOutput")}
        </pre>
        {!expanded && expandable && (
          <div
            className={cn(
              "pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t",
              tone === "error"
                ? "from-red-950/90 via-red-950/70 to-transparent"
                : "from-zinc-950 via-zinc-950/80 to-transparent",
            )}
          />
        )}
      </div>

      {expandable && (
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className={cn(
            "flex w-full items-center justify-center gap-1 border-t px-3 py-2 text-[11px] transition-colors",
            tone === "error"
              ? "border-red-500/20 text-red-200/80 hover:bg-red-950/30"
              : "border-zinc-800/80 text-zinc-400 hover:bg-zinc-900",
          )}
        >
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {expanded ? t("actionShowLess") : t("actionShowMore")}
        </button>
      )}
    </div>
  );
}
