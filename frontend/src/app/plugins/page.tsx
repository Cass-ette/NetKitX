"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PluginMeta } from "@/types";

export default function PluginsPage() {
  const token = useAuth((s) => s.token);
  const [plugins, setPlugins] = useState<PluginMeta[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api<PluginMeta[]>("/api/v1/plugins", { token })
      .then(setPlugins)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Plugins</h1>
        <p className="text-muted-foreground">Manage installed plugins</p>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {plugins.map((p) => (
            <Card key={p.name}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{p.name}</CardTitle>
                  <Badge variant="default">active</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-3">{p.description}</p>
                <div className="flex gap-2">
                  <Badge variant="outline">{p.engine}</Badge>
                  <Badge variant="outline">{p.category}</Badge>
                  <Badge variant="outline">v{p.version}</Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Add Plugin</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            To add a plugin, create a directory in <code className="rounded bg-muted px-1">plugins/</code> with
            a <code className="rounded bg-muted px-1">plugin.yaml</code> and
            a <code className="rounded bg-muted px-1">main.py</code> file, then restart the server.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
