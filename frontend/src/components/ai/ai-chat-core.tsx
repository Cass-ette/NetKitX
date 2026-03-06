"use client";

import { useEffect, useRef, useState, useCallback } from "react";
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
  RotateCcw,
  Play,
  Square,
} from "lucide-react";
import { useAIChatStore } from "@/lib/ai-chat-store";
import { useAIChat } from "@/hooks/use-ai-chat";
import { useTranslations } from "@/i18n/use-translations";
import { stripActionTags } from "@/lib/agent-utils";
import { AgentActionCard } from "@/components/ai/agent-action-card";
import { AgentStatusBar } from "@/components/ai/agent-status-bar";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface AIChatCoreProps {
  variant?: "full" | "panel";
}

export function AIChatCore({ variant = "full" }: AIChatCoreProps) {
  const { t } = useTranslations("ai");
  const {
    setMode,
    setAgentMode,
    setInput,
    clearChat,
  } = useAIChatStore();

  const {
    messages,
    input,
    loading,
    error,
    mode,
    agentMode,
    currentTurn,
    maxTurns,
    handleSend,
    handleStop,
    handleConfirmAction,
    handleKeyDown,
  } = useAIChat();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { token } = useAuth();

  // Container status for terminal mode
  const [containerStatus, setContainerStatus] = useState<{exists: boolean; status?: string} | null>(null);
  const [containerLoading, setContainerLoading] = useState(false);

  const fetchContainerStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/terminal/session`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) setContainerStatus(await res.json());
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => {
    if (agentMode === "terminal") fetchContainerStatus();
  }, [agentMode, fetchContainerStatus]);

  const handleStartContainer = async () => {
    setContainerLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/terminal/session`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) setContainerStatus(await res.json());
    } finally {
      setContainerLoading(false);
    }
  };

  const handleStopContainer = async () => {
    setContainerLoading(true);
    try {
      await fetch(`${API_BASE}/api/v1/terminal/session`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setContainerStatus({ exists: false });
    } finally {
      setContainerLoading(false);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const isPanel = variant === "panel";

  // Not configured state
  if (error === "not_configured") {
    return (
      <div className="flex flex-col items-center justify-center h-full space-y-4">
        <Bot className="h-12 w-12 text-muted-foreground" />
        <Badge variant="secondary">{t("notConfigured")}</Badge>
        <p className="text-muted-foreground text-sm text-center">{t("noConfig")}</p>
        <Button variant="outline" asChild>
          <Link href="/settings">
            <Settings className="mr-2 h-4 w-4" />
            {t("goToSettings")}
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className={`flex flex-col ${isPanel ? "h-full" : "h-[calc(100vh-8rem)]"}`}>
      {/* Header - only show in full page mode */}
      {!isPanel && (
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

            <Button variant="ghost" size="icon" onClick={clearChat} title={t("newChat")}>
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Panel-mode compact controls */}
      {isPanel && (
        <div className="px-3 pb-2 flex items-center gap-1.5 flex-wrap">
          {/* Agent mode - icon only */}
          <div className="flex items-center gap-0.5 rounded-lg border p-0.5">
            <Button
              variant={agentMode === "chat" ? "default" : "ghost"}
              size="icon"
              className="h-7 w-7"
              onClick={() => setAgentMode("chat")}
              title={t("agentChat")}
            >
              <MessageSquare className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant={agentMode === "semi_auto" ? "default" : "ghost"}
              size="icon"
              className="h-7 w-7"
              onClick={() => setAgentMode("semi_auto")}
              title={t("agentSemiAuto")}
            >
              <Cpu className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant={agentMode === "full_auto" ? "default" : "ghost"}
              size="icon"
              className="h-7 w-7"
              onClick={() => setAgentMode("full_auto")}
              title={t("agentFullAuto")}
            >
              <Zap className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant={agentMode === "terminal" ? "default" : "ghost"}
              size="icon"
              className="h-7 w-7"
              onClick={() => setAgentMode("terminal")}
              title={t("agentTerminal")}
            >
              <Terminal className="h-3.5 w-3.5" />
            </Button>
          </div>

          {/* Security mode */}
          <div className="flex items-center gap-0.5 rounded-lg border p-0.5">
            <Button
              variant={mode === "defense" ? "default" : "ghost"}
              size="icon"
              className="h-7 w-7"
              onClick={() => setMode("defense")}
              title={t("modeDefense")}
            >
              <Shield className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant={mode === "offense" ? "default" : "ghost"}
              size="icon"
              className="h-7 w-7"
              onClick={() => setMode("offense")}
              title={t("modeOffense")}
            >
              <Swords className="h-3.5 w-3.5" />
            </Button>
          </div>

          <div className="flex-1" />
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={clearChat} title={t("newChat")}>
            <RotateCcw className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Messages */}
      <div className={`flex-1 overflow-y-auto space-y-4 ${isPanel ? "px-3 pb-2" : "pb-4"}`}>
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-3">
            <Bot className={`text-muted-foreground ${isPanel ? "h-8 w-8" : "h-10 w-10"}`} />
            <p className="text-muted-foreground text-sm max-w-md">{t("welcome")}</p>
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

            <div className={`flex flex-col gap-2 ${isPanel ? "max-w-[85%]" : "max-w-[80%]"}`}>
              {/* Text bubble */}
              {(msg.content.trim() || (msg.role === "assistant" && !msg.action)) && (
                <Card className={`${msg.role === "user" ? "bg-primary text-primary-foreground" : ""}`}>
                  <CardContent className="p-3">
                    {msg.role === "assistant" ? (
                      <div className="prose prose-sm dark:prose-invert max-w-none">
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
        <p className={`text-sm text-destructive mb-2 ${isPanel ? "px-3" : ""}`}>{error}</p>
      )}

      {/* Container status banner (terminal mode only) */}
      {agentMode === "terminal" && (
        <div className={`flex items-center gap-2 py-1 px-2 rounded-md border text-sm mb-1 ${isPanel ? "mx-3" : ""} ${containerStatus?.status === "running" ? "border-green-500/30 bg-green-500/10" : "border-yellow-500/30 bg-yellow-500/10"}`}>
          <Terminal className="h-3 w-3 shrink-0" />
          <span className="text-muted-foreground flex-1">
            Sandbox:{" "}
            <Badge variant={containerStatus?.status === "running" ? "default" : "secondary"} className="text-xs h-4">
              {containerStatus?.status ?? "unknown"}
            </Badge>
          </span>
          {containerStatus?.status === "running" ? (
            <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={handleStopContainer} disabled={containerLoading}>
              {containerLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Square className="h-3 w-3" />}
            </Button>
          ) : (
            <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={handleStartContainer} disabled={containerLoading}>
              {containerLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            </Button>
          )}
        </div>
      )}

      {/* Agent status bar */}
      {agentMode !== "chat" && (
        <div className={isPanel ? "px-3" : ""}>
          <AgentStatusBar
            agentMode={agentMode}
            turn={currentTurn}
            maxTurns={maxTurns}
            running={loading}
            onStop={handleStop}
          />
        </div>
      )}

      {/* Input */}
      <div className={`flex gap-2 pt-2 border-t ${isPanel ? "px-3 pb-3" : ""}`}>
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
