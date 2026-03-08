"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useTranslations } from "@/i18n/use-translations";
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
import { Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import type { SessionListResponse, AgentSession } from "@/types";

const PAGE_SIZE = 20;

function modeBadge(mode: string) {
  const colors: Record<string, string> = {
    semi_auto: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
    full_auto: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
    terminal: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
  };
  return <Badge className={colors[mode] || ""}>{mode.replace("_", "-")}</Badge>;
}

function statusBadge(status: string) {
  const variant = status === "completed" ? "default" : status === "failed" ? "destructive" : "outline";
  return <Badge variant={variant}>{status}</Badge>;
}

function securityBadge(mode: string) {
  return (
    <Badge variant={mode === "offense" ? "destructive" : "secondary"}>
      {mode}
    </Badge>
  );
}

export default function SessionsPage() {
  const { t } = useTranslations("knowledge");
  const token = useAuth((s) => s.token);
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isPending, startTransition] = useTransition();

  const fetchSessions = async (off: number) => {
    if (!token) return;
    try {
      const data = await api<SessionListResponse>(
        `/api/v1/sessions?offset=${off}&limit=${PAGE_SIZE}`,
        { token },
      );
      setSessions(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
    }
  };

  useEffect(() => {
    startTransition(async () => {
      await fetchSessions(offset);
    });
  }, [token, offset]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDelete = async (id: number) => {
    if (!token) return;
    try {
      await api(`/api/v1/sessions/${id}`, { method: "DELETE", token });
      startTransition(async () => {
        await fetchSessions(offset);
      });
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t("sessions")}</h1>
        <p className="text-muted-foreground">{t("sessionsDescription")}</p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40%]">{t("title")}</TableHead>
              <TableHead>{t("mode")}</TableHead>
              <TableHead>{t("security")}</TableHead>
              <TableHead>{t("turns")}</TableHead>
              <TableHead>{t("status")}</TableHead>
              <TableHead>{t("date")}</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sessions.length === 0 && !isPending ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  {t("noSessions")}
                </TableCell>
              </TableRow>
            ) : (
              sessions.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link
                      href={`/sessions/${s.id}`}
                      className="hover:underline font-medium line-clamp-1"
                    >
                      {s.title}
                    </Link>
                  </TableCell>
                  <TableCell>{modeBadge(s.agent_mode)}</TableCell>
                  <TableCell>{securityBadge(s.security_mode)}</TableCell>
                  <TableCell>{s.total_turns}</TableCell>
                  <TableCell>{statusBadge(s.status)}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(s.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleDelete(s.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {t("totalSessions", { count: total })}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm py-1.5">
              {currentPage} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
