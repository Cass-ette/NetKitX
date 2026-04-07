"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bot, Brain, Puzzle, History } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";

interface Stats {
  plugins_count: number;
}

export default function DashboardPage() {
  const token = useAuth((s) => s.token);
  const { t } = useTranslations("dashboard");
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    if (!token) return;
    api<Stats>("/api/v1/stats", { token }).then(setStats).catch(() => {});
  }, [token]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground mt-2">{t("subtitle")}</p>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Link href="/ai-chat">
          <Card className="cursor-pointer hover:border-primary transition-colors">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t("aiChat")}</CardTitle>
              <Bot className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">{t("aiChatDesc")}</p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/sessions">
          <Card className="cursor-pointer hover:border-primary transition-colors">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t("sessions")}</CardTitle>
              <History className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">{t("sessionsDesc")}</p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/knowledge">
          <Card className="cursor-pointer hover:border-primary transition-colors">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t("knowledge")}</CardTitle>
              <Brain className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">{t("knowledgeDesc")}</p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/plugins">
          <Card className="cursor-pointer hover:border-primary transition-colors">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t("plugins")}</CardTitle>
              <Puzzle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.plugins_count ?? "-"}</div>
              <p className="text-xs text-muted-foreground">{t("loadedPlugins")}</p>
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* Getting Started */}
      <Card>
        <CardHeader>
          <CardTitle>{t("gettingStarted")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{t("gettingStartedDesc")}</p>
          <div className="flex gap-2">
            <Link href="/settings">
              <Button variant="outline">{t("configureAI")}</Button>
            </Link>
            <Link href="/ai-chat">
              <Button>{t("startChat")}</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
