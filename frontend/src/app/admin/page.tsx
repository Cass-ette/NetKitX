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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import {
  Users,
  ShieldCheck,
  ListTodo,
  Puzzle,
  MoreHorizontal,
  Loader2,
} from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

interface AdminUser {
  id: number;
  username: string;
  email: string;
  role: string;
  avatar_url?: string | null;
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
  const { t } = useTranslations("admin");
  const token = useAuth((s) => s.token);
  const currentUser = useAuth((s) => s.user);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);

  const loadData = useCallback(async () => {
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

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRoleChange = async (userId: number, newRole: string) => {
    if (!token) return;
    try {
      await api("/api/v1/admin/users/" + userId + "/role", {
        method: "PATCH",
        token,
        body: JSON.stringify({ role: newRole }),
      });
      await loadData();
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
      await loadData();
    } catch (err) {
      console.error("Failed to delete user:", err);
    }
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

      {/* User Management */}
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
                    {new Date(user.created_at).toLocaleDateString()}
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

      {/* Delete Confirmation */}
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
    </div>
  );
}
