"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useTranslations } from "@/i18n/use-translations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, User, Bot, Sparkles, Loader2, BookOpen, GitBranch } from "lucide-react";
import { AgentActionCard } from "@/components/ai/agent-action-card";
import ReactMarkdown from "react-markdown";
import type { AgentSessionDetail, SessionTurn, AgentAction, AgentActionResult, KnowledgeEntry } from "@/types";

interface KnowledgeListResponse {
  items: KnowledgeEntry[];
  total: number;
}

export default function SessionDetailPage() {
  const { t } = useTranslations("knowledge");
  const { t: tAi } = useTranslations("ai");
  const token = useAuth((s) => s.token);
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [session, setSession] = useState<AgentSessionDetail | null>(null);
  const [isPending, startTransition] = useTransition();
  const [knowledge, setKnowledge] = useState<KnowledgeEntry | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [savingWorkflow, setSavingWorkflow] = useState(false);

  const fetchKnowledge = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api<KnowledgeListResponse>("/api/v1/knowledge", { token });
      const entry = data.items.find((e) => e.session_id === Number(sessionId));
      if (entry) setKnowledge(entry);
      return entry;
    } catch {
      return null;
    }
  }, [token, sessionId]);

  useEffect(() => {
    if (!token || !sessionId) return;
    startTransition(async () => {
      try {
        const data = await api<AgentSessionDetail>(
          `/api/v1/sessions/${sessionId}`,
          { token },
        );
        setSession(data);
      } catch (err) {
        console.error("Failed to fetch session:", err);
      }
      await fetchKnowledge();
    });
  }, [token, sessionId, fetchKnowledge]);

  const handleExtract = async () => {
    if (!token || extracting) return;
    setExtracting(true);
    try {
      await api(`/api/v1/sessions/${sessionId}/extract`, {
        method: "POST",
        token,
      });
      // Poll for completion
      const poll = setInterval(async () => {
        const entry = await fetchKnowledge();
        if (entry && entry.extraction_status !== "processing") {
          clearInterval(poll);
          setExtracting(false);
        }
      }, 3000);
      // Stop polling after 2 minutes
      setTimeout(() => {
        clearInterval(poll);
        setExtracting(false);
      }, 120_000);
    } catch (err) {
      console.error("Extract failed:", err);
      setExtracting(false);
    }
  };

  const handleSaveWorkflow = async () => {
    if (!token || savingWorkflow) return;
    setSavingWorkflow(true);
    try {
      const data = await api<{ id: number }>(
        `/api/v1/workflows/from-session/${sessionId}`,
        { method: "POST", token },
      );
      router.push(`/workflows/${data.id}`);
    } catch (err) {
      console.error("Save workflow failed:", err);
      setSavingWorkflow(false);
    }
  };

  if (isPending || !session) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">{t("loading")}</p>
      </div>
    );
  }

  const isProcessing = extracting || knowledge?.extraction_status === "processing";
  const hasReport = knowledge?.extraction_status === "success" && knowledge.learning_report;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push("/sessions")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold truncate">{session.title}</h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline">{session.agent_mode.replace("_", "-")}</Badge>
            <Badge variant={session.security_mode === "offense" ? "destructive" : "secondary"}>
              {session.security_mode}
            </Badge>
            <Badge variant={session.status === "completed" ? "default" : session.status === "failed" ? "destructive" : "outline"}>
              {session.status}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {new Date(session.created_at).toLocaleString()}
            </span>
            <span className="text-sm text-muted-foreground">
              {tAi("agentTurnUnlimited", { turn: session.total_turns })}
            </span>
          </div>
        </div>
        <Button
          onClick={handleSaveWorkflow}
          disabled={savingWorkflow || session.status !== "completed"}
          variant="outline"
          size="sm"
        >
          {savingWorkflow ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" />{t("saving")}</>
          ) : (
            <><GitBranch className="h-4 w-4 mr-2" />{t("saveAsWorkflow")}</>
          )}
        </Button>
        <Button
          onClick={handleExtract}
          disabled={isProcessing || hasReport !== false}
          variant={hasReport ? "outline" : "default"}
          size="sm"
        >
          {isProcessing ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" />{t("extracting")}</>
          ) : hasReport ? (
            <><BookOpen className="h-4 w-4 mr-2" />{t("reportReady")}</>
          ) : (
            <><Sparkles className="h-4 w-4 mr-2" />{t("generateReport")}</>
          )}
        </Button>
      </div>

      {/* Learning Report */}
      {hasReport && (
        <Card className="border-primary/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              {t("learningReport")}
            </CardTitle>
          </CardHeader>
          <CardContent className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{knowledge!.learning_report}</ReactMarkdown>
          </CardContent>
        </Card>
      )}

      {/* Knowledge Summary (if extracted) */}
      {knowledge?.extraction_status === "success" && (
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{knowledge.target_type}</Badge>
          <Badge variant="outline">{knowledge.vulnerability_type}</Badge>
          <Badge variant={knowledge.outcome === "success" ? "default" : knowledge.outcome === "failed" ? "destructive" : "secondary"}>
            {knowledge.outcome}
          </Badge>
          {knowledge.tags?.map((tag) => (
            <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
          ))}
        </div>
      )}

      {/* Turns */}
      <div className="space-y-4">
        {session.turns.map((turn: SessionTurn) => (
          <TurnCard key={turn.id} turn={turn} />
        ))}
      </div>
    </div>
  );
}

function TurnCard({ turn }: { turn: SessionTurn }) {
  if (turn.role === "user") {
    return (
      <div className="flex gap-3 items-start">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <User className="h-4 w-4 text-primary" />
        </div>
        <Card className="flex-1 max-w-[80%]">
          <CardContent className="p-3">
            <p className="text-sm whitespace-pre-wrap">{turn.content}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (turn.role === "action_result") {
    const result = turn.action_result as AgentActionResult | undefined;
    if (!result) return null;
    return (
      <div className="flex gap-3 items-start pl-11">
        <Card className="flex-1 max-w-[80%] border-muted">
          <CardContent className="p-3 text-xs space-y-1">
            {result.error ? (
              <p className="text-destructive">{result.error}</p>
            ) : result.items ? (
              <p className="text-green-600">{result.items.length} result(s)</p>
            ) : result.stdout ? (
              <pre className="font-mono text-muted-foreground bg-muted rounded p-1.5 max-h-32 overflow-y-auto whitespace-pre-wrap">
                {result.stdout.slice(0, 1000)}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      </div>
    );
  }

  // assistant
  return (
    <div className="flex gap-3 items-start">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
        <Bot className="h-4 w-4" />
      </div>
      <div className="flex-1 max-w-[80%] space-y-2">
        {turn.content && (
          <Card>
            <CardContent className="p-3 prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown>{turn.content}</ReactMarkdown>
            </CardContent>
          </Card>
        )}
        {turn.action && (
          Array.isArray(turn.action) ? (
            <div className="space-y-2">
              {(turn.action as AgentAction[]).map((act, idx) => (
                <AgentActionCard
                  key={idx}
                  action={act}
                  status={(turn.action_status as "proposed" | "executing" | "done" | "skipped") || "done"}
                  result={Array.isArray(turn.action_result) ? (turn.action_result as AgentActionResult[])[idx] : undefined}
                />
              ))}
            </div>
          ) : (
            <AgentActionCard
              action={turn.action as AgentAction}
              status={(turn.action_status as "proposed" | "executing" | "done" | "skipped") || "done"}
              result={turn.action_result as AgentActionResult | undefined}
            />
          )
        )}
      </div>
    </div>
  );
}
