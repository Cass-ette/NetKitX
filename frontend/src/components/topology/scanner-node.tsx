"use client";

import { Handle, Position } from "@xyflow/react";
import { Radar } from "lucide-react";

interface ScannerNodeData {
  label: string;
  total_results: number;
}

export function ScannerNode({ data }: { data: ScannerNodeData }) {
  return (
    <div className="rounded-full border-2 border-primary bg-primary/10 px-6 py-4 shadow-md">
      <div className="flex flex-col items-center gap-1">
        <Radar className="h-6 w-6 text-primary" />
        <span className="font-bold text-sm">{data.label}</span>
        <span className="text-xs text-muted-foreground">
          {data.total_results} results
        </span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-primary" />
    </div>
  );
}
