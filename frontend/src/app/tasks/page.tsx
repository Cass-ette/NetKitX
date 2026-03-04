"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
import type { Task } from "@/types";

export default function TasksPage() {
  const token = useAuth((s) => s.token);
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
        <h1 className="text-3xl font-bold tracking-tight">Tasks</h1>
        <p className="text-muted-foreground">Task execution history</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No tasks yet. Go to <Link href="/tools" className="text-primary underline">Tools</Link> to run a scan.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Plugin</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Results</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task) => {
                  const duration =
                    task.started_at && task.finished_at
                      ? `${((new Date(task.finished_at).getTime() - new Date(task.started_at).getTime()) / 1000).toFixed(1)}s`
                      : task.status === "running"
                        ? "running..."
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
                          {task.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs">
                        {new Date(task.created_at).toLocaleString()}
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
