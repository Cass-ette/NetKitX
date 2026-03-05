"use client";

import { Handle, Position } from "@xyflow/react";
import { Monitor } from "lucide-react";

interface HostNodeData {
  label: string;
  host: string;
  ports: number[];
  services: string[];
}

export function HostNode({ data }: { data: HostNodeData }) {
  return (
    <div className="rounded-lg border bg-card px-4 py-3 shadow-sm min-w-[160px]">
      <Handle type="target" position={Position.Top} className="!bg-primary" />
      <div className="flex items-center gap-2 mb-1">
        <Monitor className="h-4 w-4 text-muted-foreground" />
        <span className="font-semibold text-sm">{data.label}</span>
      </div>
      {data.ports.length > 0 && (
        <div className="text-xs text-muted-foreground">
          Ports: {data.ports.slice(0, 5).join(", ")}
          {data.ports.length > 5 && ` +${data.ports.length - 5}`}
        </div>
      )}
      {data.services.length > 0 && (
        <div className="text-xs text-muted-foreground">
          {data.services.slice(0, 3).join(", ")}
          {data.services.length > 3 && ` +${data.services.length - 3}`}
        </div>
      )}
    </div>
  );
}
