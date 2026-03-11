"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useTranslations } from "@/i18n/use-translations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Trash2, ChevronLeft, ChevronRight, GitBranch } from "lucide-react";
import type { WorkflowListResponse, WorkflowListItem } from "@/types";

const PAGE_SIZE = 20;

export default function WorkflowsPage() {
  const { t } = useTranslations("workflows");
  const token = useAuth((s) => s.token);
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isPending, startTransition] = useTransition();

  const fetchWorkflows = async (off: number) => {
    if (!token) return;
    try {
      const data = await api<WorkflowListResponse>(
        `/api/v1/workflows?offset=${off}&limit=${PAGE_SIZE}`,
        { token },
      );
      setWorkflows(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to fetch workflows:", err);
    }
  };

  useEffect(() => {
    startTransition(async () => {
      await fetchWorkflows(offset);
    });
  }, [token, offset]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDelete = async (id: number) => {
    if (!token) return;
    try {
      await api(`/api/v1/workflows/${id}`, { method: "DELETE", token });
      startTransition(async () => {
        await fetchWorkflows(offset);
      });
    } catch (err) {
      console.error("Failed to delete workflow:", err);
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </div>

      {workflows.length === 0 && !isPending ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <GitBranch className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>{t("noWorkflows")}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {workflows.map((w) => (
            <Link key={w.id} href={`/workflows/${w.id}`}>
              <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-base line-clamp-1">{w.name}</CardTitle>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0"
                      onClick={(e) => {
                        e.preventDefault();
                        handleDelete(w.id);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  {w.description && (
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {w.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline" className="text-xs">
                      {t("nodeCount", { count: w.node_count })}
                    </Badge>
                    {w.session_id && (
                      <Badge variant="secondary" className="text-xs">
                        Session #{w.session_id}
                      </Badge>
                    )}
                    <Badge
                      variant={w.status === "running" ? "default" : "outline"}
                      className="text-xs"
                    >
                      {w.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {new Date(w.created_at).toLocaleDateString()}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {t("totalWorkflows", { count: total })}
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
