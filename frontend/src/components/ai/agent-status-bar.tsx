"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Square, Zap } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import type { AgentMode } from "@/types";

interface AgentStatusBarProps {
  agentMode: AgentMode;
  turn: number;
  maxTurns: number;
  running: boolean;
  onStop: () => void;
}

const MODE_LABELS: Record<AgentMode, string> = {
  chat: "Chat",
  semi_auto: "Semi-Auto",
  full_auto: "Full-Auto",
  terminal: "Terminal",
};

const MODE_COLORS: Record<AgentMode, string> = {
  chat: "secondary",
  semi_auto: "outline",
  full_auto: "default",
  terminal: "destructive",
};

export function AgentStatusBar({
  agentMode,
  turn,
  maxTurns,
  running,
  onStop,
}: AgentStatusBarProps) {
  const { t } = useTranslations("ai");

  return (
    <div className="flex items-center gap-2 px-2 py-1 rounded-md bg-muted/60 text-xs mb-1">
      <Zap className="h-3 w-3 text-primary" />
      <Badge variant={MODE_COLORS[agentMode] as "secondary" | "outline" | "default" | "destructive"} className="text-xs h-5">
        {MODE_LABELS[agentMode]}
      </Badge>
      {running && turn > 0 && (
        <span className="text-muted-foreground">
          {maxTurns > 0
            ? t("agentTurn", { turn, max: maxTurns })
            : t("agentTurnUnlimited", { turn })}
        </span>
      )}
      <div className="flex-1" />
      {running && (
        <Button
          size="sm"
          variant="ghost"
          className="h-5 text-xs px-2 text-destructive hover:text-destructive"
          onClick={onStop}
        >
          <Square className="h-3 w-3 mr-1" />
          {t("agentStop")}
        </Button>
      )}
    </div>
  );
}
