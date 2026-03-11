"use client";

import { useEffect, useState, useCallback, use } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Terminal, X } from "lucide-react";
import type { PluginMeta, PluginSession } from "@/types";
import { SessionTerminal } from "@/components/plugin-session/session-terminal";
import { useTranslations } from "@/i18n/use-translations";

export default function SessionPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const token = useAuth((s) => s.token);
  const { t } = useTranslations("tools");
  const { t: tc } = useTranslations("common");
  const [tool, setTool] = useState<PluginMeta | null>(null);
  const [formData, setFormData] = useState<Record<string, string | number>>({});
  const [session, setSession] = useState<PluginSession | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch tool metadata
  useEffect(() => {
    api<PluginMeta>(`/api/v1/tools/${slug}`, { token: token || undefined })
      .then((meta) => {
        setTool(meta);
        const defaults: Record<string, string | number> = {};
        for (const p of meta.params) {
          if (p.default !== undefined && p.default !== null) {
            defaults[p.name] = p.default as string | number;
          }
        }
        setFormData(defaults);
      })
      .catch(() => setError("Tool not found"));
  }, [slug, token]);

  const handleConnect = useCallback(async () => {
    if (!tool || !token) return;
    setConnecting(true);
    setError(null);

    try {
      const sess = await api<PluginSession>("/api/v1/plugin-sessions", {
        method: "POST",
        token,
        body: JSON.stringify({ plugin_name: tool.name, params: formData }),
      });
      setSession(sess);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setConnecting(false);
    }
  }, [tool, token, formData]);

  const handleDisconnect = useCallback(async () => {
    if (!session || !token) return;
    try {
      await api(`/api/v1/plugin-sessions/${session.session_id}`, {
        method: "DELETE",
        token,
      });
    } catch {
      // ignore cleanup errors
    }
    setSession(null);
  }, [session, token]);

  // Cleanup session on page unload
  useEffect(() => {
    return () => {
      if (session && token) {
        fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/plugin-sessions/${session.session_id}`,
          {
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` },
            keepalive: true,
          },
        ).catch(() => {});
      }
    };
  }, [session, token]);

  if (error && !tool) {
    return <p className="text-destructive">{error}</p>;
  }
  if (!tool) {
    return <p className="text-muted-foreground">{tc("loading")}</p>;
  }

  // Only show session-relevant params (url, password, shell_type, timeout)
  const sessionParams = tool.params.filter((p) =>
    ["url", "password", "shell_type", "timeout"].includes(p.name),
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {tool.description}
          </h1>
          <div className="mt-1 flex gap-2">
            <Badge>{tool.category}</Badge>
            <Badge variant="outline">v{tool.version}</Badge>
            <Badge variant="secondary">
              <Terminal className="mr-1 h-3 w-3" />
              Session Mode
            </Badge>
          </div>
        </div>
        {session && (
          <Button variant="destructive" size="sm" onClick={handleDisconnect}>
            <X className="mr-2 h-4 w-4" />
            Disconnect
          </Button>
        )}
      </div>

      {/* Connection Form — shown when no active session */}
      {!session && (
        <Card>
          <CardHeader>
            <CardTitle>{t("parameters")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              {sessionParams.map((param) => (
                <div key={param.name} className="space-y-2">
                  <Label htmlFor={param.name}>
                    {param.label || param.name}
                    {param.required && <span className="text-destructive ml-1">*</span>}
                  </Label>
                  {param.type === "select" && param.options ? (
                    <select
                      id={param.name}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={formData[param.name] ?? ""}
                      onChange={(e) => setFormData({ ...formData, [param.name]: e.target.value })}
                    >
                      {param.options.map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      id={param.name}
                      type={param.type === "number" ? "number" : "text"}
                      placeholder={param.placeholder || ""}
                      value={formData[param.name] ?? ""}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          [param.name]: param.type === "number" ? Number(e.target.value) : e.target.value,
                        })
                      }
                    />
                  )}
                </div>
              ))}
            </div>
            <Button onClick={handleConnect} disabled={connecting} className="mt-4">
              {connecting ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Connecting...</>
              ) : (
                <><Terminal className="mr-2 h-4 w-4" /> Start Session</>
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Session Terminal */}
      {session && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Session: {session.session_id.slice(0, 8)}...
              <Badge variant="outline">{tool.name}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SessionTerminal
              sessionId={session.session_id}
              pluginName={tool.name}
              onDisconnect={() => setSession(null)}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
