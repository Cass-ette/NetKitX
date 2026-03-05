"use client";

import { useEffect, useState, useCallback, use } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { connectTaskWS } from "@/lib/ws";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Play, Loader2, Download, FileText, FileDown } from "lucide-react";
import type { PluginMeta, Task } from "@/types";
import { TaskTerminal } from "@/components/terminal/task-terminal";
import { API_BASE } from "@/lib/api";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface WSEvent {
  type: string;
  data: Record<string, unknown>;
}

export default function ToolDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const token = useAuth((s) => s.token);
  const [tool, setTool] = useState<PluginMeta | null>(null);
  const [formData, setFormData] = useState<Record<string, string | number>>({});
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ percent: number; msg: string } | null>(null);
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<number | null>(null);
  const [terminalOpen, setTerminalOpen] = useState(false);

  // Fetch tool metadata
  useEffect(() => {
    api<PluginMeta>(`/api/v1/tools/${slug}`, { token: token || undefined })
      .then((t) => {
        setTool(t);
        // Initialize form defaults
        const defaults: Record<string, string | number> = {};
        for (const p of t.params) {
          if (p.default !== undefined && p.default !== null) {
            defaults[p.name] = p.default as string | number;
          }
        }
        setFormData(defaults);
      })
      .catch(() => setError("Tool not found"));
  }, [slug, token]);

  const handleRun = useCallback(async () => {
    if (!tool || !token) return;
    setRunning(true);
    setResults([]);
    setError(null);
    setProgress({ percent: 0, msg: "Starting..." });
    setTaskStatus("pending");
    setTerminalOpen(true);

    try {
      // Create task
      const task = await api<Task>("/api/v1/tasks", {
        method: "POST",
        token,
        body: JSON.stringify({ plugin_name: tool.name, params: formData }),
      });

      setTaskId(task.id);

      // Connect WebSocket for real-time updates
      const ws = connectTaskWS(
        task.id,
        (event: WSEvent) => {
          switch (event.type) {
            case "progress":
              setProgress({
                percent: (event.data.percent as number) || 0,
                msg: (event.data.msg as string) || "",
              });
              break;
            case "result":
              setResults((prev) => [...prev, event.data]);
              break;
            case "log":
              // Handled by TaskTerminal component
              break;
            case "status":
              setTaskStatus(event.data.status as string);
              if (event.data.status === "done" || event.data.status === "failed") {
                setRunning(false);
                ws.close();
              }
              break;
            case "error":
              setError((event.data.error as string) || "Unknown error");
              setRunning(false);
              setTaskStatus("failed");
              ws.close();
              break;
          }
        },
        () => setRunning(false),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task");
      setRunning(false);
    }
  }, [tool, token, formData]);

  const handleExport = useCallback(
    (format: "html" | "pdf") => {
      if (!taskId || !token) return;
      const url = `${API_BASE}/api/v1/reports/${taskId}/export?format=${format}`;
      const a = document.createElement("a");
      a.href = url;
      a.target = "_blank";
      // For PDF, use fetch to add auth header and trigger download
      fetch(url, { headers: { Authorization: `Bearer ${token}` } })
        .then((res) => {
          if (!res.ok) throw new Error("Export failed");
          return res.blob();
        })
        .then((blob) => {
          const blobUrl = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = blobUrl;
          link.download = `report-${taskId}.${format}`;
          link.click();
          URL.revokeObjectURL(blobUrl);
        })
        .catch(() => setError("Failed to export report"));
    },
    [taskId, token],
  );

  if (error && !tool) {
    return <p className="text-destructive">{error}</p>;
  }
  if (!tool) {
    return <p className="text-muted-foreground">Loading...</p>;
  }

  const columns = tool.output?.columns || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{tool.description}</h1>
          <div className="mt-1 flex gap-2">
            <Badge>{tool.category}</Badge>
            <Badge variant="outline">{tool.engine}</Badge>
            <Badge variant="outline">v{tool.version}</Badge>
          </div>
        </div>
        {taskStatus === "done" && taskId && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Download className="mr-2 h-4 w-4" />
                Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => handleExport("html")}>
                <FileText className="mr-2 h-4 w-4" />
                HTML Report
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport("pdf")}>
                <FileDown className="mr-2 h-4 w-4" />
                PDF Report
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Parameter Form */}
      <Card>
        <CardHeader>
          <CardTitle>Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            {tool.params.map((param) => (
              <div key={param.name} className="space-y-2">
                <Label htmlFor={param.name}>
                  {param.label || param.name}
                  {param.required && <span className="text-destructive ml-1">*</span>}
                </Label>
                {param.type === "select" && param.options ? (
                  <select
                    id={param.name}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={formData[param.name] ?? ""}
                    onChange={(e) => setFormData({ ...formData, [param.name]: e.target.value })}
                  >
                    {param.options.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : (
                  <Input
                    id={param.name}
                    type={param.type === "number" ? "number" : "text"}
                    placeholder={param.placeholder || ""}
                    value={formData[param.name] ?? ""}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        [param.name]: param.type === "number" ? Number(e.target.value) : e.target.value,
                      })
                    }
                  />
                )}
              </div>
            ))}
          </div>
          <Button onClick={handleRun} disabled={running} className="mt-4">
            {running ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Running...</>
            ) : (
              <><Play className="mr-2 h-4 w-4" /> Run</>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Progress */}
      {progress && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>{progress.msg}</span>
                <span>{progress.percent}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-secondary">
                <div
                  className="h-2 rounded-full bg-primary transition-all duration-300"
                  style={{ width: `${progress.percent}%` }}
                />
              </div>
              {taskStatus && (
                <Badge variant={taskStatus === "done" ? "default" : taskStatus === "failed" ? "destructive" : "secondary"}>
                  {taskStatus}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Terminal Panel */}
      {taskId && (
        <Card>
          <CardHeader className="cursor-pointer" onClick={() => setTerminalOpen(!terminalOpen)}>
            <CardTitle className="flex items-center justify-between">
              <span>Terminal</span>
              <Badge variant="outline">{terminalOpen ? "Collapse" : "Expand"}</Badge>
            </CardTitle>
          </CardHeader>
          {terminalOpen && (
            <CardContent>
              <TaskTerminal taskId={taskId} />
            </CardContent>
          )}
        </Card>
      )}

      {/* Results Table */}
      {results.length > 0 && columns.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Results ({results.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((col) => (
                    <TableHead key={col.key}>{col.label}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((row, i) => (
                  <TableRow key={i}>
                    {columns.map((col) => (
                      <TableCell key={col.key}>{String(row[col.key] ?? "")}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* JSON fallback if no columns defined */}
      {results.length > 0 && columns.length === 0 && (
        <Card>
          <CardHeader><CardTitle>Results ({results.length})</CardTitle></CardHeader>
          <CardContent>
            <pre className="max-h-96 overflow-auto rounded bg-muted p-3 text-xs">
              {JSON.stringify(results, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
