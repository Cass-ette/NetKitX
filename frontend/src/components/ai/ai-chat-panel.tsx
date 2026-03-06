"use client";

import { Bot, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAIChatStore } from "@/lib/ai-chat-store";
import { useTranslations } from "@/i18n/use-translations";
import { AIChatCore } from "@/components/ai/ai-chat-core";
import { AIChatResizeHandle } from "@/components/ai/ai-chat-resize-handle";

export function AIChatPanel() {
  const { panelOpen, panelWidth, setPanelOpen } = useAIChatStore();
  const { t } = useTranslations("ai");

  if (!panelOpen) return null;

  return (
    <div
      className="relative flex-shrink-0 border-l bg-background flex flex-col h-full"
      style={{ width: panelWidth }}
    >
      <AIChatResizeHandle />

      {/* Panel header */}
      <div className="flex items-center justify-between h-12 px-3 border-b flex-shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4" />
          <span className="text-sm font-medium">{t("chat")}</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => setPanelOpen(false)}
          title={t("closePanel")}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Chat content */}
      <div className="flex-1 min-h-0 pt-2">
        <AIChatCore variant="panel" />
      </div>
    </div>
  );
}
