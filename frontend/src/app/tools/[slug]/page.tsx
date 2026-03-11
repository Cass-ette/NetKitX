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
import { Play, Loader2, Download, FileText, FileDown, Bot, Terminal } from "lucide-react";
import type { PluginMeta, Task } from "@/types";
import Link from "next/link";
import { TaskTerminal } from "@/components/terminal/task-terminal";
import { AIAnalysisSheet } from "@/components/ai/ai-analysis-sheet";
import { API_BASE } from "@/lib/api";
import { PluginUIRenderer, isRegisteredUI } from "@/components/plugin-ui/registry";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTranslations } from "@/i18n/use-translations";

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
  const { t } = useTranslations("tools");
  const { t: tc } = useTranslations("common");
  const [tool, setTool] = useState<PluginMeta | null>(null);
  const [formData, setFormData] = useState<Record<string, string | number>>({});
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ percent: number; msg: string } | null>(null);
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<number | null>(null);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [aiSheetOpen, setAiSheetOpen] = useState(false);

  // Fetch tool metadata
  useEffect(() => {
    api<PluginMeta>(`/api/v1/tools/${slug}`, { token: token || undefined })
      .then((meta) => {
        setTool(meta);
        // Initialize form defaults
        const defaults: Record<string, string | number> = {};
        for (const p of meta.params) {
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
    setProgress({ percent: 0, msg: t("starting") });
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
      setError(err instanceof Error ? err.message : t("failedToCreateTask"));
      setRunning(false);
    }
  }, [tool, token, formData, t]);

  const handleExport = useCallback(
    (format: "html" | "pdf") => {
      if (!taskId || !token) return;
      const url = `${API_BASE}/api/v1/reports/${taskId}/export?format=${format}`;
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
        .catch(() => setError(t("failedToExport")));
    },
    [taskId, token, t],
  );

  if (error && !tool) {
    return <p className="text-destructive">{error}</p>;
  }
  if (!tool) {
    return <p className="text-muted-foreground">{tc("loading")}</p>;
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
            {tool.mode === "session" && (
              <Badge variant="secondary">
                <Terminal className="mr-1 h-3 w-3" />
                Session
              </Badge>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {tool.mode === "session" && (
            <Link href={`/tools/${slug}/session`}>
              <Button variant="outline">
                <Terminal className="mr-2 h-4 w-4" />
                Session Mode
              </Button>
            </Link>
          )}
          {taskStatus === "done" && taskId && (
            <>
            <Button variant="outline" onClick={() => setAiSheetOpen(true)}>
              <Bot className="mr-2 h-4 w-4" />
              {t("aiAnalyze")}
            </Button>
            <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Download className="mr-2 h-4 w-4" />
                {t("export")}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => handleExport("html")}>
                <FileText className="mr-2 h-4 w-4" />
                {t("htmlReport")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport("pdf")}>
                <FileDown className="mr-2 h-4 w-4" />
                {t("pdfReport")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
            </>
          )}
        </div>
      </div>

      {/* Parameter Form */}
      <Card>
        <CardHeader>
          <CardTitle>{t("parameters")}</CardTitle>
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
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> {t("running")}</>
            ) : (
              <><Play className="mr-2 h-4 w-4" /> {t("run")}</>
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
                  {tc(`status_${taskStatus}`)}
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
              <span>{t("terminal")}</span>
              <Badge variant="outline">{terminalOpen ? t("collapse") : t("expand")}</Badge>
            </CardTitle>
          </CardHeader>
          {terminalOpen && (
            <CardContent>
              <TaskTerminal taskId={taskId} />
            </CardContent>
          )}
        </Card>
      )}

      {/* Results — custom UI or default table */}
      {results.length > 0 && (
        tool.ui_component && isRegisteredUI(tool.ui_component) ? (
          <PluginUIRenderer
            uiComponent={tool.ui_component}
            tool={tool}
            results={results}
            taskId={taskId}
            taskStatus={taskStatus}
          />
        ) : columns.length > 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>{t("results", { count: results.length })}</CardTitle>
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
        ) : (
          <Card>
            <CardHeader><CardTitle>{t("results", { count: results.length })}</CardTitle></CardHeader>
            <CardContent>
              <pre className="max-h-96 overflow-auto rounded bg-muted p-3 text-xs">
                {JSON.stringify(results, null, 2)}
              </pre>
            </CardContent>
          </Card>
        )
      )}

      {/* Topology: render even without results when task is done */}
      {tool.ui_component === "topology" && taskId && taskStatus === "done" && results.length === 0 && (
        <PluginUIRenderer
          uiComponent="topology"
          tool={tool}
          results={results}
          taskId={taskId}
          taskStatus={taskStatus}
        />
      )}

      {/* AI Analysis Sheet */}
      {taskId && (
        <AIAnalysisSheet
          open={aiSheetOpen}
          onOpenChange={setAiSheetOpen}
          taskId={taskId}
          resultPreview={
            results.length > 0
              ? JSON.stringify(results, null, 2).slice(0, 2000)
              : undefined
          }
        />
      )}
    </div>
  );
}
