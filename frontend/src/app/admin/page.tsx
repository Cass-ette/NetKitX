"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Users,
  ShieldCheck,
  ListTodo,
  Puzzle,
  MoreHorizontal,
  Loader2,
  ScrollText,
  Gauge,
  Megaphone,
  Server,
  RefreshCw,
  Plus,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type {
  AdminTask,
  AdminPlugin,
  AuditLog,
  UserQuota,
  Announcement,
  ServerStatus,
} from "@/types";

interface AdminUser {
  id: number;
  username: string;
  email: string;
  role: string;
  avatar_url?: string | null;
  max_concurrent_tasks: number;
  max_daily_tasks: number;
  created_at: string;
}

interface SystemStats {
  total_users: number;
  admin_users: number;
  regular_users: number;
  total_tasks: number;
  total_plugins: number;
}

export default function AdminPage() {
  const { t, locale } = useTranslations("admin");
  const token = useAuth((s) => s.token);
  const currentUser = useAuth((s) => s.user);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);

  // Task management
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [tasksTotal, setTasksTotal] = useState(0);
  const [taskFilter, setTaskFilter] = useState({ status: "all", plugin: "" });

  // Plugin management
  const [plugins, setPlugins] = useState<AdminPlugin[]>([]);

  // Audit log
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);

  // Quotas
  const [quotaUserId, setQuotaUserId] = useState<number | null>(null);
  const [quota, setQuota] = useState<UserQuota | null>(null);
  const [quotaEdit, setQuotaEdit] = useState({ maxConcurrent: 5, maxDaily: 100 });

  // Announcements
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [annDialog, setAnnDialog] = useState(false);
  const [annEdit, setAnnEdit] = useState<{ title: string; content: string; type: string }>({
    title: "",
    content: "",
    type: "info",
  });
  const [annEditId, setAnnEditId] = useState<number | null>(null);

  // Server status
  const [serverStatus, setServerStatus] = useState<ServerStatus | null>(null);
  const [serverLoading, setServerLoading] = useState(false);

  // ── Data Loaders ────────────────────────────────────────────────

  const loadUsers = useCallback(async () => {
    if (!token) return;
    try {
      const [usersData, statsData] = await Promise.all([
        api<AdminUser[]>("/api/v1/admin/users", { token }),
        api<SystemStats>("/api/v1/admin/stats", { token }),
      ]);
      setUsers(usersData);
      setStats(statsData);
    } catch (err) {
      console.error("Failed to load admin data:", err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadTasks = useCallback(async () => {
    if (!token) return;
    try {
      const params = new URLSearchParams();
      if (taskFilter.status && taskFilter.status !== "all") params.set("status", taskFilter.status);
      if (taskFilter.plugin) params.set("plugin_name", taskFilter.plugin);
      const qs = params.toString();
      const data = await api<{ tasks: AdminTask[]; total: number }>(
        `/api/v1/admin/tasks${qs ? "?" + qs : ""}`,
        { token }
      );
      setTasks(data.tasks);
      setTasksTotal(data.total);
    } catch (err) {
      console.error("Failed to load tasks:", err);
    }
  }, [token, taskFilter]);

  const loadPlugins = useCallback(async () => {
    if (!token) return;
    try {
      setPlugins(await api<AdminPlugin[]>("/api/v1/admin/plugins", { token }));
    } catch (err) {
      console.error("Failed to load plugins:", err);
    }
  }, [token]);

  const loadAuditLogs = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api<{ logs: AuditLog[]; total: number }>(
        "/api/v1/admin/audit-logs",
        { token }
      );
      setAuditLogs(data.logs);
      setAuditTotal(data.total);
    } catch (err) {
      console.error("Failed to load audit logs:", err);
    }
  }, [token]);

  const loadAnnouncements = useCallback(async () => {
    if (!token) return;
    try {
      setAnnouncements(
        await api<Announcement[]>("/api/v1/admin/announcements", { token })
      );
    } catch (err) {
      console.error("Failed to load announcements:", err);
    }
  }, [token]);

  const loadServerStatus = useCallback(async () => {
    if (!token) return;
    setServerLoading(true);
    try {
      setServerStatus(await api<ServerStatus>("/api/v1/admin/server-status", { token }));
    } catch (err) {
      console.error("Failed to load server status:", err);
    } finally {
      setServerLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  // ── User Actions ────────────────────────────────────────────────

  const handleRoleChange = async (userId: number, newRole: string) => {
    if (!token) return;
    try {
      await api("/api/v1/admin/users/" + userId + "/role", {
        method: "PATCH",
        token,
        body: JSON.stringify({ role: newRole }),
      });
      await loadUsers();
    } catch (err) {
      console.error("Failed to change role:", err);
    }
  };

  const handleDelete = async () => {
    if (!token || !deleteTarget) return;
    try {
      await api("/api/v1/admin/users/" + deleteTarget.id, {
        method: "DELETE",
        token,
      });
      setDeleteTarget(null);
      await loadUsers();
    } catch (err) {
      console.error("Failed to delete user:", err);
    }
  };

  // ── Task Actions ────────────────────────────────────────────────

  const handleCancelTask = async (taskId: number) => {
    if (!token) return;
    try {
      await api(`/api/v1/admin/tasks/${taskId}/cancel`, { method: "POST", token });
      await loadTasks();
    } catch (err) {
      console.error("Failed to cancel task:", err);
    }
  };

  const handleDeleteTask = async (taskId: number) => {
    if (!token) return;
    try {
      await api(`/api/v1/admin/tasks/${taskId}`, { method: "DELETE", token });
      await loadTasks();
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  };

  // ── Plugin Actions ──────────────────────────────────────────────

  const handleTogglePlugin = async (pluginName: string) => {
    if (!token) return;
    try {
      await api(`/api/v1/admin/plugins/${pluginName}/toggle`, { method: "PATCH", token });
      await loadPlugins();
    } catch (err) {
      console.error("Failed to toggle plugin:", err);
    }
  };

  // ── Quota Actions ───────────────────────────────────────────────

  const loadQuota = async (userId: number) => {
    if (!token) return;
    try {
      const q = await api<UserQuota>(`/api/v1/admin/users/${userId}/quota`, { token });
      setQuota(q);
      setQuotaUserId(userId);
      setQuotaEdit({ maxConcurrent: q.max_concurrent_tasks, maxDaily: q.max_daily_tasks });
    } catch (err) {
      console.error("Failed to load quota:", err);
    }
  };

  const handleSaveQuota = async () => {
    if (!token || !quotaUserId) return;
    try {
      await api(`/api/v1/admin/users/${quotaUserId}/quota`, {
        method: "PATCH",
        token,
        body: JSON.stringify({
          max_concurrent_tasks: quotaEdit.maxConcurrent,
          max_daily_tasks: quotaEdit.maxDaily,
        }),
      });
      await loadQuota(quotaUserId);
    } catch (err) {
      console.error("Failed to update quota:", err);
    }
  };

  // ── Announcement Actions ────────────────────────────────────────

  const handleSaveAnnouncement = async () => {
    if (!token) return;
    try {
      if (annEditId) {
        await api(`/api/v1/admin/announcements/${annEditId}`, {
          method: "PATCH",
          token,
          body: JSON.stringify(annEdit),
        });
      } else {
        await api("/api/v1/admin/announcements", {
          method: "POST",
          token,
          body: JSON.stringify(annEdit),
        });
      }
      setAnnDialog(false);
      setAnnEditId(null);
      setAnnEdit({ title: "", content: "", type: "info" });
      await loadAnnouncements();
    } catch (err) {
      console.error("Failed to save announcement:", err);
    }
  };

  const handleToggleAnnouncement = async (ann: Announcement) => {
    if (!token) return;
    try {
      await api(`/api/v1/admin/announcements/${ann.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ active: !ann.active }),
      });
      await loadAnnouncements();
    } catch (err) {
      console.error("Failed to toggle announcement:", err);
    }
  };

  const handleDeleteAnnouncement = async (annId: number) => {
    if (!token) return;
    try {
      await api(`/api/v1/admin/announcements/${annId}`, { method: "DELETE", token });
      await loadAnnouncements();
    } catch (err) {
      console.error("Failed to delete announcement:", err);
    }
  };

  // ── Tab Change Handler ──────────────────────────────────────────

  const handleTabChange = (tab: string) => {
    if (tab === "tasks") loadTasks();
    else if (tab === "plugins") loadPlugins();
    else if (tab === "audit") loadAuditLogs();
    else if (tab === "announcements") loadAnnouncements();
    else if (tab === "server") loadServerStatus();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const statCards = [
    { key: "totalUsers", value: stats?.total_users ?? 0, icon: Users },
    { key: "adminUsers", value: stats?.admin_users ?? 0, icon: ShieldCheck },
    { key: "totalTasks", value: stats?.total_tasks ?? 0, icon: ListTodo },
    { key: "totalPlugins", value: stats?.total_plugins ?? 0, icon: Puzzle },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((s) => (
          <Card key={s.key}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">{t(s.key)}</CardTitle>
              <s.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{s.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="users" onValueChange={handleTabChange}>
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="users"><Users className="mr-1 h-4 w-4" />{t("tabUsers")}</TabsTrigger>
          <TabsTrigger value="tasks"><ListTodo className="mr-1 h-4 w-4" />{t("tabTasks")}</TabsTrigger>
          <TabsTrigger value="plugins"><Puzzle className="mr-1 h-4 w-4" />{t("tabPlugins")}</TabsTrigger>
          <TabsTrigger value="audit"><ScrollText className="mr-1 h-4 w-4" />{t("tabAudit")}</TabsTrigger>
          <TabsTrigger value="quotas"><Gauge className="mr-1 h-4 w-4" />{t("tabQuotas")}</TabsTrigger>
          <TabsTrigger value="announcements"><Megaphone className="mr-1 h-4 w-4" />{t("tabAnnouncements")}</TabsTrigger>
          <TabsTrigger value="server"><Server className="mr-1 h-4 w-4" />{t("tabServer")}</TabsTrigger>
        </TabsList>

        {/* ── Users Tab ────────────────────────────────────────── */}
        <TabsContent value="users">
          <Card>
            <CardHeader>
              <CardTitle>{t("userManagement")}</CardTitle>
              <CardDescription>{t("userManagementDesc")}</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("username")}</TableHead>
                    <TableHead>{t("email")}</TableHead>
                    <TableHead>{t("role")}</TableHead>
                    <TableHead>{t("createdAt")}</TableHead>
                    <TableHead className="w-12">{t("actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">{user.username}</TableCell>
                      <TableCell>{user.email}</TableCell>
                      <TableCell>
                        <Badge variant={user.role === "admin" ? "default" : "secondary"}>
                          {t(user.role)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(user.created_at).toLocaleDateString(locale)}
                      </TableCell>
                      <TableCell>
                        {user.id !== currentUser?.id && (
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              {user.role === "user" ? (
                                <DropdownMenuItem onClick={() => handleRoleChange(user.id, "admin")}>
                                  {t("makeAdmin")}
                                </DropdownMenuItem>
                              ) : (
                                <DropdownMenuItem onClick={() => handleRoleChange(user.id, "user")}>
                                  {t("removeAdmin")}
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() => setDeleteTarget(user)}
                              >
                                {t("deleteUser")}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Tasks Tab ────────────────────────────────────────── */}
        <TabsContent value="tasks">
          <Card>
            <CardHeader>
              <CardTitle>{t("taskManagement")}</CardTitle>
              <CardDescription>{t("taskManagementDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Select
                  value={taskFilter.status}
                  onValueChange={(v) => setTaskFilter((f) => ({ ...f, status: v }))}
                >
                  <SelectTrigger className="w-[160px]">
                    <SelectValue placeholder={t("filterByStatus")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t("allStatuses")}</SelectItem>
                    <SelectItem value="pending">{t("pending")}</SelectItem>
                    <SelectItem value="running">{t("running")}</SelectItem>
                    <SelectItem value="done">{t("done")}</SelectItem>
                    <SelectItem value="failed">{t("failed")}</SelectItem>
                  </SelectContent>
                </Select>
                <Button variant="outline" size="sm" onClick={loadTasks}>
                  <RefreshCw className="mr-1 h-4 w-4" />{t("refresh")}
                </Button>
              </div>

              {tasks.length === 0 ? (
                <p className="text-sm text-muted-foreground py-8 text-center">{t("noTasks")}</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>{t("plugin")}</TableHead>
                      <TableHead>{t("status")}</TableHead>
                      <TableHead>{t("createdBy")}</TableHead>
                      <TableHead>{t("createdAt")}</TableHead>
                      <TableHead className="w-12">{t("actions")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tasks.map((task) => (
                      <TableRow key={task.id}>
                        <TableCell>{task.id}</TableCell>
                        <TableCell className="font-medium">{task.plugin_name}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              task.status === "done" ? "default" :
                              task.status === "failed" ? "destructive" :
                              task.status === "running" ? "secondary" : "outline"
                            }
                          >
                            {t(task.status)}
                          </Badge>
                        </TableCell>
                        <TableCell>{task.created_by_username ?? "-"}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(task.created_at).toLocaleString(locale)}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              {(task.status === "pending" || task.status === "running") && (
                                <DropdownMenuItem onClick={() => handleCancelTask(task.id)}>
                                  {t("cancelTask")}
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() => handleDeleteTask(task.id)}
                              >
                                {t("deleteTask")}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
              <p className="text-xs text-muted-foreground">{tasksTotal} {t("totalTasks").toLowerCase()}</p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Plugins Tab ──────────────────────────────────────── */}
        <TabsContent value="plugins">
          <Card>
            <CardHeader>
              <CardTitle>{t("pluginManagement")}</CardTitle>
              <CardDescription>{t("pluginManagementDesc")}</CardDescription>
            </CardHeader>
            <CardContent>
              {plugins.length === 0 ? (
                <p className="text-sm text-muted-foreground py-8 text-center">{t("noPlugins")}</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("plugin")}</TableHead>
                      <TableHead>{t("version")}</TableHead>
                      <TableHead>{t("category")}</TableHead>
                      <TableHead>{t("engine")}</TableHead>
                      <TableHead>{t("usageCount")}</TableHead>
                      <TableHead>{t("status")}</TableHead>
                      <TableHead className="w-12">{t("actions")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {plugins.map((p) => (
                      <TableRow key={p.name}>
                        <TableCell className="font-medium">{p.name}</TableCell>
                        <TableCell>{p.version}</TableCell>
                        <TableCell><Badge variant="outline">{p.category}</Badge></TableCell>
                        <TableCell>{p.engine}</TableCell>
                        <TableCell>{p.usage_count}</TableCell>
                        <TableCell>
                          <Badge variant={p.enabled ? "default" : "secondary"}>
                            {p.enabled ? t("enabled") : t("disabled")}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleTogglePlugin(p.name)}
                          >
                            {p.enabled ? t("disable") : t("enable")}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Audit Tab ────────────────────────────────────────── */}
        <TabsContent value="audit">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{t("auditLog")}</CardTitle>
                  <CardDescription>{t("auditLogDesc")}</CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={loadAuditLogs}>
                  <RefreshCw className="mr-1 h-4 w-4" />{t("refresh")}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {auditLogs.length === 0 ? (
                <p className="text-sm text-muted-foreground py-8 text-center">{t("noAuditLogs")}</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("username")}</TableHead>
                      <TableHead>{t("action")}</TableHead>
                      <TableHead>{t("targetType")}</TableHead>
                      <TableHead>{t("targetId")}</TableHead>
                      <TableHead>{t("createdAt")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {auditLogs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell className="font-medium">{log.username}</TableCell>
                        <TableCell><Badge variant="outline">{log.action}</Badge></TableCell>
                        <TableCell>{log.target_type}</TableCell>
                        <TableCell>{log.target_id ?? "-"}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(log.created_at).toLocaleString(locale)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
              <p className="text-xs text-muted-foreground mt-2">{auditTotal} {t("auditLog").toLowerCase()}</p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Quotas Tab ───────────────────────────────────────── */}
        <TabsContent value="quotas">
          <Card>
            <CardHeader>
              <CardTitle>{t("quotaManagement")}</CardTitle>
              <CardDescription>{t("quotaManagementDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2 items-end">
                <div>
                  <Label>{t("username")}</Label>
                  <Select
                    value={quotaUserId?.toString() ?? "none"}
                    onValueChange={(v) => {
                      if (v !== "none") loadQuota(Number(v));
                    }}
                  >
                    <SelectTrigger className="w-[200px]">
                      <SelectValue placeholder={t("filterByUser")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">{t("filterByUser")}</SelectItem>
                      {users.map((u) => (
                        <SelectItem key={u.id} value={u.id.toString()}>
                          {u.username}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {quota && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">{t("maxConcurrent")}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Input
                        type="number"
                        value={quotaEdit.maxConcurrent}
                        onChange={(e) =>
                          setQuotaEdit((q) => ({ ...q, maxConcurrent: Number(e.target.value) }))
                        }
                      />
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">{t("maxDaily")}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Input
                        type="number"
                        value={quotaEdit.maxDaily}
                        onChange={(e) =>
                          setQuotaEdit((q) => ({ ...q, maxDaily: Number(e.target.value) }))
                        }
                      />
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">{t("currentRunning")}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{quota.current_running_tasks}</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">{t("tasksToday")}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{quota.tasks_today}</div>
                    </CardContent>
                  </Card>
                </div>
              )}

              {quota && (
                <Button onClick={handleSaveQuota}>
                  {t("saveQuota")}
                </Button>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Announcements Tab ────────────────────────────────── */}
        <TabsContent value="announcements">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{t("announcementManagement")}</CardTitle>
                  <CardDescription>{t("announcementManagementDesc")}</CardDescription>
                </div>
                <Button
                  size="sm"
                  onClick={() => {
                    setAnnEditId(null);
                    setAnnEdit({ title: "", content: "", type: "info" });
                    setAnnDialog(true);
                  }}
                >
                  <Plus className="mr-1 h-4 w-4" />{t("newAnnouncement")}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {announcements.length === 0 ? (
                <p className="text-sm text-muted-foreground py-8 text-center">{t("noAnnouncements")}</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("announcementTitle")}</TableHead>
                      <TableHead>{t("announcementType")}</TableHead>
                      <TableHead>{t("status")}</TableHead>
                      <TableHead>{t("createdAt")}</TableHead>
                      <TableHead className="w-24">{t("actions")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {announcements.map((ann) => (
                      <TableRow key={ann.id}>
                        <TableCell className="font-medium">{ann.title}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              ann.type === "error" ? "destructive" :
                              ann.type === "warning" ? "secondary" : "outline"
                            }
                          >
                            {t(ann.type)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleToggleAnnouncement(ann)}
                          >
                            <Badge variant={ann.active ? "default" : "secondary"}>
                              {ann.active ? t("active") : t("inactive")}
                            </Badge>
                          </Button>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(ann.created_at).toLocaleDateString(locale)}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setAnnEditId(ann.id);
                                setAnnEdit({
                                  title: ann.title,
                                  content: ann.content,
                                  type: ann.type,
                                });
                                setAnnDialog(true);
                              }}
                            >
                              {t("editAnnouncement")}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => handleDeleteAnnouncement(ann.id)}
                            >
                              {t("deleteAnnouncement")}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Server Tab ───────────────────────────────────────── */}
        <TabsContent value="server">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{t("serverStatus")}</CardTitle>
                  <CardDescription>{t("serverStatusDesc")}</CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={loadServerStatus} disabled={serverLoading}>
                  {serverLoading ? (
                    <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-1 h-4 w-4" />
                  )}
                  {t("refresh")}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {serverStatus ? (
                <>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t("cpu")}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="text-2xl font-bold">{serverStatus.cpu_percent}%</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t("memory")}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="text-2xl font-bold">{serverStatus.memory_percent}%</div>
                        <p className="text-xs text-muted-foreground">
                          {serverStatus.memory_used_mb} / {serverStatus.memory_total_mb} MB
                        </p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t("disk")}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="text-2xl font-bold">{serverStatus.disk_percent}%</div>
                        <p className="text-xs text-muted-foreground">
                          {serverStatus.disk_used_gb} / {serverStatus.disk_total_gb} GB
                        </p>
                      </CardContent>
                    </Card>
                  </div>

                  <div>
                    <h3 className="text-sm font-medium mb-3">{t("services")}</h3>
                    <div className="space-y-2">
                      {serverStatus.services.map((svc) => (
                        <div
                          key={svc.name}
                          className="flex items-center justify-between rounded-md border px-4 py-2"
                        >
                          <span className="font-medium">{svc.name}</span>
                          <div className="flex items-center gap-2">
                            {svc.status === "ok" ? (
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                            ) : (
                              <XCircle className="h-4 w-4 text-destructive" />
                            )}
                            <Badge variant={svc.status === "ok" ? "default" : "destructive"}>
                              {svc.status === "ok" ? t("ok") : t("error")}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground py-8 text-center">
                  {t("refresh")}
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Delete User Confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("deleteUserTitle")}</DialogTitle>
            <DialogDescription>
              {t("deleteUserConfirm").replace("{{username}}", deleteTarget?.username ?? "")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              {t("cancel")}
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              {t("delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Announcement Create/Edit Dialog */}
      <Dialog open={annDialog} onOpenChange={setAnnDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {annEditId ? t("editAnnouncement") : t("newAnnouncement")}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>{t("announcementTitle")}</Label>
              <Input
                value={annEdit.title}
                onChange={(e) => setAnnEdit((a) => ({ ...a, title: e.target.value }))}
              />
            </div>
            <div>
              <Label>{t("announcementContent")}</Label>
              <Textarea
                value={annEdit.content}
                onChange={(e) => setAnnEdit((a) => ({ ...a, content: e.target.value }))}
                rows={4}
              />
            </div>
            <div>
              <Label>{t("announcementType")}</Label>
              <Select
                value={annEdit.type}
                onValueChange={(v) => setAnnEdit((a) => ({ ...a, type: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="info">{t("info")}</SelectItem>
                  <SelectItem value="warning">{t("warning")}</SelectItem>
                  <SelectItem value="error">{t("error")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAnnDialog(false)}>
              {t("cancel")}
            </Button>
            <Button onClick={handleSaveAnnouncement}>
              {annEditId ? t("updateAnnouncement") : t("createAnnouncement")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
