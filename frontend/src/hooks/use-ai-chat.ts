"use client";

import { useCallback, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { useAIChatStore } from "@/lib/ai-chat-store";
import { API_BASE } from "@/lib/api";
import { useTranslations } from "@/i18n/use-translations";
import type { ChatMessage, AgentAction, AgentActionResult } from "@/types";

export function useAIChat() {
  const token = useAuth((s) => s.token);
  const { t, locale } = useTranslations("ai");

  const {
    messages,
    input,
    loading,
    error,
    mode,
    agentMode,
    currentTurn,
    maxTurns,
    setMessages,
    setInput,
    setLoading,
    setError,
    setCurrentTurn,
    setCurrentSessionId,
  } = useAIChatStore();

  const abortRef = useRef<AbortController | null>(null);
  const doneReasonRef = useRef<string | null>(null);

  // Stop agent loop
  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setLoading(false);
  }, [setLoading]);

  // Chat mode send
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
                const snap = assistantContent;
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = { role: "assistant", content: snap };
                  return updated;
                });
              }
            } catch { /* skip */ }
          }
          if (streamDone) break;
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          setLoading(false);
          return;
        }
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    },
    [token, mode, locale, setMessages, setError],
  );

  // Agent SSE stream processor
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

          if (event === "session_start") {
            setCurrentSessionId(data.session_id as number);
          } else if (event === "text") {
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
              return [...updated, { role: "assistant", content: "" }];
            });
          } else if (event === "action_error") {
            const errorType = data.error_type as string;
            if (errorType === "malformed") {
              assistantContent = "";
              setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
            }
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
    [token, agentMode, mode, locale, maxTurns, setMessages, setError, setCurrentTurn, setCurrentSessionId],
  );

  // Main send handler
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

        if (reason === "error") {
          const notice = t("agentErrorStopped");
          if (isTrailingEmpty) {
            const updated = [...prev];
            updated[updated.length - 1] = { role: "assistant", content: notice };
            return updated;
          }
          return [...prev, { role: "assistant", content: notice }];
        }

        if (isTrailingEmpty) {
          return prev.slice(0, -1);
        }
        return prev;
      });
      setLoading(false);
    }
  }, [token, input, messages, loading, agentMode, handleChatSend, processAgentStream, t, maxTurns, setMessages, setInput, setLoading, setError, setCurrentTurn]);

  // Mode A confirm handler
  const handleConfirmAction = useCallback(
    async (approved: boolean, action: AgentAction, msgIdx: number) => {
      if (loading) return;

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

      const apiMessages = messages.filter((m) => m.content.trim()).slice(0, msgIdx);

      try {
        await processAgentStream(apiMessages, { approved, action });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          setLoading(false);
          return;
        }
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [loading, messages, processAgentStream, setMessages, setLoading, setError],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return {
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
  };
}
