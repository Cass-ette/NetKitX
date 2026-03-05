"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Task } from "@/types";
import { useTranslations } from "@/i18n/use-translations";

export default function TasksPage() {
  const token = useAuth((s) => s.token);
  const { t, locale } = useTranslations("tasks");
  const { t: tc } = useTranslations("common");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api<Task[]>("/api/v1/tasks", { token })
      .then(setTasks)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-muted-foreground">{tc("loading")}</p>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("noTasksYet").split("{{toolsLink}}")[0]}
              <Link href="/tools" className="text-primary underline">{t("toolsLinkText")}</Link>
              {t("noTasksYet").split("{{toolsLink}}")[1]}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("id")}</TableHead>
                  <TableHead>{t("plugin")}</TableHead>
                  <TableHead>{t("status")}</TableHead>
                  <TableHead>{t("created")}</TableHead>
                  <TableHead>{t("duration")}</TableHead>
                  <TableHead>{t("results")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task) => {
                  const duration =
                    task.started_at && task.finished_at
                      ? `${((new Date(task.finished_at).getTime() - new Date(task.started_at).getTime()) / 1000).toFixed(1)}s`
                      : task.status === "running"
                        ? t("runningDuration")
                        : "-";
                  const resultCount =
                    task.result && "items" in task.result
                      ? (task.result.items as unknown[]).length
                      : "-";
                  return (
                    <TableRow key={task.id}>
                      <TableCell>#{task.id}</TableCell>
                      <TableCell className="font-medium">{task.plugin_name}</TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            task.status === "done" ? "default" :
                            task.status === "failed" ? "destructive" :
                            task.status === "running" ? "secondary" : "outline"
                          }
                        >
                          {tc(`status_${task.status}`)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs">
                        {new Date(task.created_at).toLocaleString(locale)}
                      </TableCell>
                      <TableCell>{duration}</TableCell>
                      <TableCell>{resultCount}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
