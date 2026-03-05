"use client";

import { useState, useRef, useCallback } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Loader2, Bot, Settings, Shield, Swords } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";
import { useTranslations } from "@/i18n/use-translations";
import Link from "next/link";

interface AIAnalysisSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  taskId: number;
  resultPreview?: string;
}

export function AIAnalysisSheet({
  open,
  onOpenChange,
  taskId,
  resultPreview,
}: AIAnalysisSheetProps) {
  const token = useAuth((s) => s.token);
  const { t } = useTranslations("ai");
  const [customPrompt, setCustomPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"defense" | "offense">("offense");
  const abortRef = useRef<AbortController | null>(null);

  const handleAnalyze = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setResponse("");
    setError(null);

    abortRef.current = new AbortController();

    try {
      const res = await fetch(`${API_BASE}/api/v1/ai/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          task_id: taskId,
          content: "",
          custom_prompt: customPrompt || undefined,
          mode,
        }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        if (body.detail === "AI not configured") {
          setError("not_configured");
        } else {
          setError(body.detail || `Error ${res.status}`);
        }
        setLoading(false);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);
          if (data === "[DONE]") break;
          try {
            const parsed = JSON.parse(data);
            if (parsed.content) {
              setResponse((prev) => prev + parsed.content);
            }
          } catch {
            // skip
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [token, taskId, customPrompt, mode]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            {t("analyze")}
          </SheetTitle>
        </SheetHeader>

        <div className="mt-4 space-y-4">
          {/* Mode selector */}
          <div className="flex items-center gap-1 rounded-lg border p-1">
            <Button
              variant={mode === "defense" ? "default" : "ghost"}
              size="sm"
              className="flex-1"
              onClick={() => setMode("defense")}
            >
              <Shield className="mr-1 h-4 w-4" />
              {t("modeDefense")}
            </Button>
            <Button
              variant={mode === "offense" ? "default" : "ghost"}
              size="sm"
              className="flex-1"
              onClick={() => setMode("offense")}
            >
              <Swords className="mr-1 h-4 w-4" />
              {t("modeOffense")}
            </Button>
          </div>

          {/* Result preview */}
          {resultPreview && (
            <div>
              <p className="text-sm font-medium mb-1">{t("resultPreview")}</p>
              <pre className="max-h-40 overflow-auto rounded bg-muted p-2 text-xs">
                {resultPreview}
              </pre>
            </div>
          )}

          {/* Custom prompt */}
          <div>
            <p className="text-sm font-medium mb-1">{t("customPrompt")}</p>
            <Textarea
              placeholder={t("customPromptPlaceholder")}
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              rows={3}
            />
          </div>

          {/* Analyze button */}
          <Button onClick={handleAnalyze} disabled={loading} className="w-full">
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t("analyzing")}
              </>
            ) : (
              <>
                <Bot className="mr-2 h-4 w-4" />
                {t("analyze")}
              </>
            )}
          </Button>

          {/* Error states */}
          {error === "not_configured" && (
            <div className="rounded-md border p-4 text-center space-y-2">
              <Badge variant="secondary">{t("notConfigured")}</Badge>
              <p className="text-sm text-muted-foreground">{t("noConfig")}</p>
              <Button variant="outline" size="sm" asChild>
                <Link href="/settings">
                  <Settings className="mr-2 h-4 w-4" />
                  {t("goToSettings")}
                </Link>
              </Button>
            </div>
          )}
          {error && error !== "not_configured" && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          {/* AI response */}
          {response && (
            <div className="rounded-md border p-3">
              <pre className="whitespace-pre-wrap text-sm">{response}</pre>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
