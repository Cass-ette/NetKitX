"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Save, Trash2 } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { AISettings } from "@/types";

export default function SettingsPage() {
  const { t } = useTranslations("settings");
  const token = useAuth((s) => s.token);

  const [aiProvider, setAiProvider] = useState("claude");
  const [aiApiKey, setAiApiKey] = useState("");
  const [aiModel, setAiModel] = useState("claude-sonnet-4-20250514");
  const [aiConfigured, setAiConfigured] = useState(false);
  const [aiMasked, setAiMasked] = useState("");
  const [aiSaving, setAiSaving] = useState(false);
  const [aiMsg, setAiMsg] = useState<string | null>(null);

  const loadAiSettings = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api<AISettings>("/api/v1/ai/settings", { token });
      setAiProvider(data.provider);
      setAiModel(data.model);
      setAiMasked(data.api_key_masked);
      setAiConfigured(true);
    } catch {
      setAiConfigured(false);
    }
  }, [token]);

  useEffect(() => {
    loadAiSettings();
  }, [loadAiSettings]);

  const handleAiSave = async () => {
    if (!token || !aiApiKey) return;
    setAiSaving(true);
    setAiMsg(null);
    try {
      await api("/api/v1/ai/settings", {
        method: "PUT",
        token,
        body: JSON.stringify({
          provider: aiProvider,
          api_key: aiApiKey,
          model: aiModel,
        }),
      });
      setAiApiKey("");
      setAiMsg(t("aiSaved"));
      await loadAiSettings();
    } catch (err) {
      setAiMsg(err instanceof Error ? err.message : "Error");
    } finally {
      setAiSaving(false);
    }
  };

  const handleAiDelete = async () => {
    if (!token) return;
    setAiSaving(true);
    setAiMsg(null);
    try {
      await api("/api/v1/ai/settings", { method: "DELETE", token });
      setAiConfigured(false);
      setAiMasked("");
      setAiMsg(t("aiDeleted"));
    } catch (err) {
      setAiMsg(err instanceof Error ? err.message : "Error");
    } finally {
      setAiSaving(false);
    }
  };

  const defaultModels: Record<string, string> = {
    claude: "claude-sonnet-4-20250514",
    deepseek: "deepseek-chat",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("apiConnection")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>{t("backendUrl")}</Label>
            <Input value={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} readOnly />
          </div>
          <div className="space-y-2">
            <Label>{t("status")}</Label>
            <div><Badge variant="default">{t("connected")}</Badge></div>
          </div>
        </CardContent>
      </Card>

      {/* AI Configuration Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t("aiConfig")}</CardTitle>
              <CardDescription>{t("aiConfigDesc")}</CardDescription>
            </div>
            <Badge variant={aiConfigured ? "default" : "secondary"}>
              {aiConfigured ? t("connected") : t("aiProvider")}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {aiConfigured && (
            <div className="rounded-md bg-muted p-3 text-sm space-y-1">
              <p><strong>{t("aiProvider")}:</strong> {aiProvider}</p>
              <p><strong>{t("aiModel")}:</strong> {aiModel}</p>
              <p><strong>{t("aiApiKey")}:</strong> {aiMasked}</p>
            </div>
          )}

          <div className="space-y-2">
            <Label>{t("aiProvider")}</Label>
            <Select
              value={aiProvider}
              onValueChange={(v) => {
                setAiProvider(v);
                setAiModel(defaultModels[v] || "");
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="claude">Claude (Anthropic)</SelectItem>
                <SelectItem value="deepseek">DeepSeek</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>{t("aiApiKey")}</Label>
            <Input
              type="password"
              placeholder={aiConfigured ? "Enter new key to update..." : "sk-..."}
              value={aiApiKey}
              onChange={(e) => setAiApiKey(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label>{t("aiModel")}</Label>
            <Input
              placeholder="e.g. claude-sonnet-4-20250514"
              value={aiModel}
              onChange={(e) => setAiModel(e.target.value)}
            />
          </div>

          {aiMsg && (
            <p className="text-sm text-muted-foreground">{aiMsg}</p>
          )}

          <div className="flex gap-2">
            <Button onClick={handleAiSave} disabled={aiSaving || !aiApiKey}>
              {aiSaving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              {t("aiSave")}
            </Button>
            {aiConfigured && (
              <Button variant="destructive" onClick={handleAiDelete} disabled={aiSaving}>
                <Trash2 className="mr-2 h-4 w-4" />
                {t("aiDelete")}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("about")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm"><strong>NetKitX</strong> - {t("extensibleToolkit")}</p>
          <p className="text-sm text-muted-foreground">{t("version", { version: "0.1.0" })}</p>
          <p className="text-sm text-muted-foreground">
            {t("pluginDirectory")} <code className="rounded bg-muted px-1">plugins/</code>
          </p>
          <p className="text-sm text-muted-foreground">
            {t("engineDirectory")} <code className="rounded bg-muted px-1">engines/bin/</code>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
