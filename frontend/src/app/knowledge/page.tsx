"use client";

import { useEffect, useState, useTransition } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useTranslations } from "@/i18n/use-translations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { BookOpen, ChevronDown, ChevronUp, ExternalLink, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { KnowledgeEntry } from "@/types";
import Link from "next/link";

interface KnowledgeListResponse {
  items: KnowledgeEntry[];
  total: number;
}

export default function KnowledgePage() {
  const { t } = useTranslations("knowledge");
  const token = useAuth((s) => s.token);
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [isPending, startTransition] = useTransition();
  const [expanded, setExpanded] = useState<number | null>(null);

  const fetchEntries = () => {
    if (!token) return;
    startTransition(async () => {
      try {
        const data = await api<KnowledgeListResponse>("/api/v1/knowledge", { token });
        setEntries(data.items);
        setTotal(data.total);
      } catch (err) {
        console.error("Failed to fetch knowledge:", err);
      }
    });
  };

  useEffect(() => {
    fetchEntries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleDelete = async (id: number) => {
    if (!token) return;
    try {
      await api(`/api/v1/knowledge/${id}`, { method: "DELETE", token });
      setEntries((prev) => prev.filter((e) => e.id !== id));
      setTotal((prev) => prev - 1);
    } catch (err) {
      console.error("Failed to delete:", err);
    }
  };

  const outcomeBadgeVariant = (outcome: string) => {
    if (outcome === "success") return "default" as const;
    if (outcome === "failed") return "destructive" as const;
    return "secondary" as const;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BookOpen className="h-6 w-6" />
          {t("knowledge")}
        </h1>
        <p className="text-muted-foreground mt-1">{t("knowledgeDescription")}</p>
        {total > 0 && (
          <p className="text-sm text-muted-foreground mt-1">
            {t("totalEntries", { count: total })}
          </p>
        )}
      </div>

      {isPending ? (
        <div className="flex items-center justify-center h-32">
          <p className="text-muted-foreground">{t("loading")}</p>
        </div>
      ) : entries.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            {t("noKnowledge")}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>{t("scenario")}</TableHead>
                <TableHead>{t("targetType")}</TableHead>
                <TableHead>{t("vulnType")}</TableHead>
                <TableHead>{t("outcome")}</TableHead>
                <TableHead>{t("date")}</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((entry) => (
                <>
                  <TableRow
                    key={entry.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
                  >
                    <TableCell>
                      {expanded === entry.id ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </TableCell>
                    <TableCell className="font-medium max-w-xs truncate">
                      {entry.scenario || entry.summary.slice(0, 80)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{entry.target_type}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{entry.vulnerability_type}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={outcomeBadgeVariant(entry.outcome)}>{entry.outcome}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(entry.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {entry.session_id && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            asChild
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Link href={`/sessions/${entry.session_id}`}>
                              <ExternalLink className="h-3.5 w-3.5" />
                            </Link>
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(entry.id);
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                  {expanded === entry.id && (
                    <TableRow key={`${entry.id}-detail`}>
                      <TableCell colSpan={7} className="bg-muted/30 p-4">
                        <div className="space-y-4">
                          {/* Tags */}
                          {entry.tags && entry.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {entry.tags.map((tag) => (
                                <Badge key={tag} variant="secondary" className="text-xs">
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                          )}
                          {/* Summary */}
                          <div>
                            <h4 className="text-sm font-semibold mb-1">{t("summary")}</h4>
                            <p className="text-sm text-muted-foreground">{entry.summary}</p>
                          </div>
                          {/* Key Findings */}
                          {entry.key_findings && (
                            <div>
                              <h4 className="text-sm font-semibold mb-1">{t("keyFindings")}</h4>
                              <p className="text-sm text-muted-foreground">{entry.key_findings}</p>
                            </div>
                          )}
                          {/* Attack Chain */}
                          {entry.attack_chain && (
                            <div>
                              <h4 className="text-sm font-semibold mb-1">{t("attackChain")}</h4>
                              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                                {entry.attack_chain}
                              </p>
                            </div>
                          )}
                          {/* Learning Report */}
                          {entry.learning_report && (
                            <Card className="border-primary/20">
                              <CardHeader className="pb-2">
                                <CardTitle className="text-sm">{t("learningReport")}</CardTitle>
                              </CardHeader>
                              <CardContent className="prose prose-sm dark:prose-invert max-w-none">
                                <ReactMarkdown>{entry.learning_report}</ReactMarkdown>
                              </CardContent>
                            </Card>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
