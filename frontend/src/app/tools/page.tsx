"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PluginMeta } from "@/types";

export default function ToolsPage() {
  const token = useAuth((s) => s.token);
  const [tools, setTools] = useState<PluginMeta[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<PluginMeta[]>("/api/v1/tools", { token: token || undefined })
      .then(setTools)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Tools</h1>
        <p className="text-muted-foreground">Available security tools</p>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading tools...</p>
      ) : tools.length === 0 ? (
        <p className="text-muted-foreground">No tools loaded. Check plugin configuration.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {tools.map((tool) => (
            <Link key={tool.name} href={`/tools/${tool.name}`}>
              <Card className="cursor-pointer hover:border-primary transition-colors h-full">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{tool.description}</CardTitle>
                    <Badge>{tool.category}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-2">{tool.name}</p>
                  <div className="flex gap-2">
                    <Badge variant="outline">{tool.engine}</Badge>
                    <Badge variant="outline">v{tool.version}</Badge>
                    <Badge variant="outline">{tool.params.length} params</Badge>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
