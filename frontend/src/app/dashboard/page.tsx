"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Wrench, ListTodo, Puzzle, Activity } from "lucide-react";
import type { Task } from "@/types";
import { useTranslations } from "@/i18n/use-translations";

interface Stats {
  tools_count: number;
  tasks_total: number;
  tasks_running: number;
  plugins_count: number;
}

export default function DashboardPage() {
  const token = useAuth((s) => s.token);
  const { t, locale } = useTranslations("dashboard");
  const { t: tc } = useTranslations("common");
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentTasks, setRecentTasks] = useState<Task[]>([]);

  useEffect(() => {
    if (!token) return;
    api<Stats>("/api/v1/stats", { token }).then(setStats).catch(() => {});
    api<Task[]>("/api/v1/tasks", { token }).then(setRecentTasks).catch(() => {});
  }, [token]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("toolsAvailable")}</CardTitle>
            <Wrench className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.tools_count ?? "..."}</div>
            <p className="text-xs text-muted-foreground">{t("registeredTools")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("totalTasks")}</CardTitle>
            <ListTodo className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.tasks_total ?? "..."}</div>
            <p className="text-xs text-muted-foreground">{t("tasksCreated")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("running")}</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.tasks_running ?? "..."}</div>
            <p className="text-xs text-muted-foreground">{t("tasksInProgress")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("plugins")}</CardTitle>
            <Puzzle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.plugins_count ?? "..."}</div>
            <p className="text-xs text-muted-foreground">{t("loadedPlugins")}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("recentTasks")}</CardTitle>
        </CardHeader>
        <CardContent>
          {recentTasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("noTasksYet").split("{{toolsLink}}")[0]}
              <Link href="/tools" className="text-primary underline">{t("toolsLinkText")}</Link>
              {t("noTasksYet").split("{{toolsLink}}")[1]}
            </p>
          ) : (
            <div className="space-y-2">
              {recentTasks.slice(0, 10).map((task) => (
                <div key={task.id} className="flex items-center justify-between rounded-md border px-4 py-2">
                  <div className="flex items-center gap-3">
                    <Badge variant={
                      task.status === "done" ? "default" :
                      task.status === "failed" ? "destructive" :
                      task.status === "running" ? "secondary" : "outline"
                    }>
                      {tc(`status_${task.status}`)}
                    </Badge>
                    <span className="text-sm font-medium">{task.plugin_name}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {new Date(task.created_at).toLocaleString(locale)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
