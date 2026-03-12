"use client";

import { Handle, Position } from "@xyflow/react";
import { Play, Flag, Puzzle, TerminalSquare, Loader2 } from "lucide-react";

interface NodeData {
  plugin?: string;
  command?: string;
  params?: Record<string, string>;
  reason?: string;
  result_summary?: string;
  status?: string;
  selected?: boolean;
  liveSummary?: string;
  error?: string;
  [key: string]: unknown;
}

interface NodeProps {
  data: NodeData;
}

export function WorkflowStartNode(_props: NodeProps) {
  return (
    <div className="flex h-[60px] w-[60px] items-center justify-center rounded-full border-2 border-green-500 bg-green-50 dark:bg-green-950 shadow-sm cursor-pointer">
      <Play className="h-5 w-5 text-green-600 dark:text-green-400" />
      <Handle type="source" position={Position.Bottom} className="!bg-green-500" />
    </div>
  );
}

export function WorkflowEndNode(_props: NodeProps) {
  return (
    <div className="flex h-[60px] w-[60px] items-center justify-center rounded-full border-2 border-muted-foreground/30 bg-muted shadow-sm cursor-pointer">
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      <Flag className="h-5 w-5 text-muted-foreground" />
    </div>
  );
}

const statusBorder: Record<string, string> = {
  pending: "border-border",
  running: "border-blue-500 animate-pulse",
  done: "border-green-500",
  failed: "border-destructive",
  skipped: "border-muted-foreground/40 opacity-50",
};

export function WorkflowPluginNode({ data }: NodeProps) {
  const status = data.status || "pending";
  const selected = data.selected;
  const params = data.params;
  const paramPreview = params
    ? Object.entries(params)
        .slice(0, 2)
        .map(([k, v]) => `${k}=${v}`)
        .join(", ")
    : "";
  const summary = data.liveSummary || data.result_summary;

  return (
    <div
      className={`w-[220px] rounded-lg border-2 bg-card px-3 py-2.5 shadow-sm cursor-pointer transition-shadow ${statusBorder[status] || statusBorder.pending} ${selected ? "ring-2 ring-primary shadow-md" : ""}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-primary" />
      <div className="flex items-center gap-2 mb-1">
        {status === "running" ? (
          <Loader2 className="h-4 w-4 shrink-0 text-blue-500 animate-spin" />
        ) : (
          <Puzzle className="h-4 w-4 shrink-0 text-primary" />
        )}
        <span className="font-semibold text-sm truncate">{data.plugin}</span>
      </div>
      {paramPreview && (
        <p className="text-xs text-muted-foreground truncate">{paramPreview}</p>
      )}
      {data.reason && (
        <p className="text-xs text-muted-foreground/70 truncate mt-0.5">
          {data.reason}
        </p>
      )}
      {status === "failed" && data.error && (
        <p className="text-xs mt-1 font-mono text-destructive truncate">
          {data.error}
        </p>
      )}
      {summary && status !== "failed" && (
        <p className="text-xs mt-1 font-mono text-green-600 dark:text-green-400 truncate">
          {summary}
        </p>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-primary" />
    </div>
  );
}

export function WorkflowShellNode({ data }: NodeProps) {
  const status = data.status || "pending";
  const selected = data.selected;
  const command = data.command || "";
  const summary = data.liveSummary || data.result_summary;

  return (
    <div
      className={`w-[220px] rounded-lg border-2 bg-card px-3 py-2.5 shadow-sm cursor-pointer transition-shadow ${statusBorder[status] || statusBorder.pending} ${selected ? "ring-2 ring-primary shadow-md" : ""}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-orange-500" />
      <div className="flex items-center gap-2 mb-1">
        {status === "running" ? (
          <Loader2 className="h-4 w-4 shrink-0 text-blue-500 animate-spin" />
        ) : (
          <TerminalSquare className="h-4 w-4 shrink-0 text-orange-500" />
        )}
        <span className="font-semibold text-sm truncate">Shell</span>
      </div>
      <p className="text-xs font-mono text-muted-foreground truncate">{command}</p>
      {data.reason && (
        <p className="text-xs text-muted-foreground/70 truncate mt-0.5">
          {data.reason}
        </p>
      )}
      {status === "failed" && data.error && (
        <p className="text-xs mt-1 font-mono text-destructive truncate">
          {data.error}
        </p>
      )}
      {summary && status !== "failed" && (
        <p className="text-xs mt-1 font-mono text-green-600 dark:text-green-400 truncate">
          {summary}
        </p>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-orange-500" />
    </div>
  );
}
