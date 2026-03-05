"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Bot,
  Send,
  Loader2,
  Settings,
  User,
  Shield,
  Swords,
  MessageSquare,
  Cpu,
  Zap,
  Terminal,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";
import { useTranslations } from "@/i18n/use-translations";
import { stripActionTags } from "@/lib/agent-utils";
import { AgentActionCard } from "@/components/ai/agent-action-card";
import { AgentStatusBar } from "@/components/ai/agent-status-bar";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage, AgentMode, AgentAction, AgentActionResult } from "@/types";

export default function AIChatPage() {
  const token = useAuth((s) => s.token);
  const { t, locale } = useTranslations("ai");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"defense" | "offense">("offense");
  const [agentMode, setAgentMode] = useState<AgentMode>("chat");
  const [currentTurn, setCurrentTurn] = useState(0);
  const maxTurns = 0; // 0 = unlimited

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const doneReasonRef = useRef<string | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Stop agent loop
  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setLoading(false);
  }, []);

  // --------------------------------------------------------------------------
  // Chat mode (existing behavior)
  // --------------------------------------------------------------------------
  const handleChatSend = useCallback(
    async (messagesToSend: ChatMessage[]) => {
      abortRef.current = new AbortController();
      try {
        const res = await fetch(`${API_BASE}/api/v1/ai/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            messages: messagesToSend.map((m) => ({ role: m.role, content: m.content })),
            mode,
            lang: locale,
          }),
          signal: abortRef.current.signal,
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          const detail = body.detail;
          if (detail === "AI not configured") {
            setError("not_configured");
          } else if (typeof detail === "string") {
            setError(detail);
          } else if (Array.isArray(detail)) {
            setError(detail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join("; "));
          } else {
            setError(`Error ${res.status}`);
          }
          return;
        }

        const reader = res.body?.getReader();
        if (!reader) return;
        const decoder = new TextDecoder();
        let buffer = "";
        let assistantContent = "";

        setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          let streamDone = false;
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6);
            if (data === "[DONE]") { streamDone = true; break; }
            try {
              const parsed = JSON.parse(data);
              if (parsed.content) {
                assistantContent += parsed.content;
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = { role: "assistant", content: assistantContent };
                  return updated;
                });
              }
            } catch { /* skip */ }
          }
          if (streamDone) break;
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    },
    [token, mode, locale],
  );

  // --------------------------------------------------------------------------
  // Agent SSE stream processor
  // --------------------------------------------------------------------------
  const processAgentStream = useCallback(
    async (
      messagesToSend: ChatMessage[],
      confirmAction?: { approved: boolean; action: AgentAction },
    ) => {
      abortRef.current = new AbortController();

      const body: Record<string, unknown> = {
        messages: messagesToSend.map((m) => ({ role: m.role, content: m.content })),
        agent_mode: agentMode,
        security_mode: mode,
        lang: locale,
        max_turns: maxTurns,
      };
      if (confirmAction) {
        body.confirm_action = confirmAction;
      }

      const res = await fetch(`${API_BASE}/api/v1/ai/agent`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
        signal: abortRef.current.signal,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        const detail = errBody.detail;
        if (detail === "AI not configured") {
          setError("not_configured");
        } else if (typeof detail === "string") {
          setError(detail);
        } else if (Array.isArray(detail)) {
          setError(detail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join("; "));
        } else {
          setError(`Error ${res.status}`);
        }
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantContent = "";

      // Add empty assistant message for streaming text
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let streamDone = false;
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6);
          if (raw === "[DONE]") { streamDone = true; break; }

          let evt: { event: string; data: Record<string, unknown> };
          try {
            evt = JSON.parse(raw);
          } catch {
            continue;
          }

          const { event, data } = evt;

          if (event === "text") {
            assistantContent += (data.content as string) || "";
            const snap = assistantContent;
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated.length - 1;
              updated[last] = { ...updated[last], content: snap };
              return updated;
            });
          } else if (event === "turn") {
            setCurrentTurn(data.turn as number);
          } else if (event === "action") {
            const action = data.action as AgentAction;
            const status = agentMode === "semi_auto" ? "proposed" : "executing";
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated.length - 1;
              updated[last] = { ...updated[last], action, actionStatus: status };
              return updated;
            });
          } else if (event === "action_status") {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated.length - 1;
              updated[last] = { ...updated[last], actionStatus: "executing" };
              return updated;
            });
          } else if (event === "action_result") {
            const result = data.result as AgentActionResult;
            assistantContent = "";
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated.length - 1;
              updated[last] = { ...updated[last], actionResult: result, actionStatus: "done" };
              // Add new empty assistant message for next turn
              return [...updated, { role: "assistant", content: "" }];
            });
          } else if (event === "waiting") {
            // semi_auto: action card already shows confirm buttons
          } else if (event === "done") {
            doneReasonRef.current = (data.reason as string) || null;
            streamDone = true;
            break;
          }
        }
        if (streamDone) break;
      }
    },
    [token, agentMode, mode, locale],
  );

  // --------------------------------------------------------------------------
  // Main send handler
  // --------------------------------------------------------------------------
  const handleSend = useCallback(async () => {
    if (!token || !input.trim() || loading) return;

    const userMsg: ChatMessage = { role: "user", content: input.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    setError(null);
    setCurrentTurn(0);

    try {
      if (agentMode === "chat") {
        await handleChatSend(newMessages);
      } else {
        await processAgentStream(newMessages);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      // Handle done reason: show notice when max turns reached
      const reason = doneReasonRef.current;
      doneReasonRef.current = null;

      setMessages((prev) => {
        const last = prev[prev.length - 1];
        const isTrailingEmpty =
          last && last.role === "assistant" && !last.content.trim() && !last.action;

        if (reason === "max_turns") {
          const notice = t("maxTurnsReached", { max: maxTurns });
          if (isTrailingEmpty) {
            const updated = [...prev];
            updated[updated.length - 1] = { role: "assistant", content: notice };
            return updated;
          }
          return [...prev, { role: "assistant", content: notice }];
        }

        // Clean up trailing empty assistant message left by action_result
        if (isTrailingEmpty) {
          return prev.slice(0, -1);
        }
        return prev;
      });
      setLoading(false);
    }
  }, [token, input, messages, loading, agentMode, handleChatSend, processAgentStream, t, maxTurns]);

  // --------------------------------------------------------------------------
  // Mode A confirm handler
  // --------------------------------------------------------------------------
  const handleConfirmAction = useCallback(
    async (approved: boolean, action: AgentAction, msgIdx: number) => {
      if (loading) return;

      // Mark card as executing or skipped
      setMessages((prev) => {
        const updated = [...prev];
        if (updated[msgIdx]) {
          updated[msgIdx] = {
            ...updated[msgIdx],
            actionStatus: approved ? "executing" : "skipped",
          };
        }
        return updated;
      });

      if (!approved) return;

      setLoading(true);
      setError(null);

      // Build messages to send: all messages before this action (raw content)
      const apiMessages = messages.filter((m) => m.content.trim()).slice(0, msgIdx);

      try {
        await processAgentStream(apiMessages, { approved, action });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [loading, messages, processAgentStream],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // --------------------------------------------------------------------------
  // Not configured state
  // --------------------------------------------------------------------------
  if (error === "not_configured") {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4">
        <Bot className="h-12 w-12 text-muted-foreground" />
        <Badge variant="secondary">{t("notConfigured")}</Badge>
        <p className="text-muted-foreground">{t("noConfig")}</p>
        <Button variant="outline" asChild>
          <Link href="/settings">
            <Settings className="mr-2 h-4 w-4" />
            {t("goToSettings")}
          </Link>
        </Button>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------
  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-3xl font-bold tracking-tight">{t("chat")}</h1>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Agent mode selector */}
          <div className="flex items-center gap-1 rounded-lg border p-1">
            <Button
              variant={agentMode === "chat" ? "default" : "ghost"}
              size="sm"
              onClick={() => setAgentMode("chat")}
              title={t("agentChat")}
            >
              <MessageSquare className="mr-1 h-4 w-4" />
              {t("agentChat")}
            </Button>
            <Button
              variant={agentMode === "semi_auto" ? "default" : "ghost"}
              size="sm"
              onClick={() => setAgentMode("semi_auto")}
              title={t("agentSemiAuto")}
            >
              <Cpu className="mr-1 h-4 w-4" />
              {t("agentSemiAuto")}
            </Button>
            <Button
              variant={agentMode === "full_auto" ? "default" : "ghost"}
              size="sm"
              onClick={() => setAgentMode("full_auto")}
              title={t("agentFullAuto")}
            >
              <Zap className="mr-1 h-4 w-4" />
              {t("agentFullAuto")}
            </Button>
            <Button
              variant={agentMode === "terminal" ? "default" : "ghost"}
              size="sm"
              onClick={() => setAgentMode("terminal")}
              title={t("agentTerminal")}
            >
              <Terminal className="mr-1 h-4 w-4" />
              {t("agentTerminal")}
            </Button>
          </div>

          {/* Security mode selector */}
          <div className="flex items-center gap-1 rounded-lg border p-1">
            <Button
              variant={mode === "defense" ? "default" : "ghost"}
              size="sm"
              onClick={() => setMode("defense")}
            >
              <Shield className="mr-1 h-4 w-4" />
              {t("modeDefense")}
            </Button>
            <Button
              variant={mode === "offense" ? "default" : "ghost"}
              size="sm"
              onClick={() => setMode("offense")}
            >
              <Swords className="mr-1 h-4 w-4" />
              {t("modeOffense")}
            </Button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-3">
            <Bot className="h-10 w-10 text-muted-foreground" />
            <p className="text-muted-foreground max-w-md">{t("welcome")}</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="h-4 w-4" />
              </div>
            )}

            <div className="flex flex-col gap-2 max-w-[80%]">
              {/* Text bubble */}
              {(msg.content.trim() || (msg.role === "assistant" && !msg.action)) && (
                <Card className={`${msg.role === "user" ? "bg-primary text-primary-foreground" : ""}`}>
                  <CardContent className="p-3">
                    {msg.role === "assistant" ? (
                      <div className="prose prose-sm dark:prose-invert max-w-none prose-pre:bg-muted prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {stripActionTags(msg.content)}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <pre className="whitespace-pre-wrap text-sm font-sans">
                        {msg.content}
                      </pre>
                    )}
                    {msg.role === "assistant" && !msg.content && !msg.action && loading && (
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        <span className="text-xs">{t("thinking")}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Action card */}
              {msg.action && msg.actionStatus && (
                <AgentActionCard
                  action={msg.action}
                  status={msg.actionStatus}
                  result={msg.actionResult}
                  onConfirm={
                    msg.actionStatus === "proposed"
                      ? (approved) => handleConfirmAction(approved, msg.action!, i)
                      : undefined
                  }
                />
              )}
            </div>

            {msg.role === "user" && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                <User className="h-4 w-4" />
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Error */}
      {error && error !== "not_configured" && (
        <p className="text-sm text-destructive mb-2">{error}</p>
      )}

      {/* Agent status bar */}
      {agentMode !== "chat" && (
        <AgentStatusBar
          agentMode={agentMode}
          turn={currentTurn}
          maxTurns={maxTurns}
          running={loading}
          onStop={handleStop}
        />
      )}

      {/* Input */}
      <div className="flex gap-2 pt-2 border-t">
        <Textarea
          placeholder={t("chatPlaceholder")}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          className="resize-none"
        />
        <Button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          size="icon"
          className="h-auto"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  );
}
