"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiUpload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { PluginMeta } from "@/types";

export default function PluginsPage() {
  const token = useAuth((s) => s.token);
  const [plugins, setPlugins] = useState<PluginMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPlugins = useCallback(() => {
    if (!token) return;
    api<PluginMeta[]>("/api/v1/plugins", { token })
      .then(setPlugins)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

  const handleUpload = async (file: File) => {
    if (!token || !file.name.endsWith(".zip")) return;
    setUploading(true);
    try {
      await apiUpload("/api/v1/plugins/upload", file, token);
      fetchPlugins();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleToggle = async (name: string, enabled: boolean) => {
    if (!token) return;
    try {
      await api(`/api/v1/plugins/${name}`, {
        token,
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      });
      fetchPlugins();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Toggle failed");
    }
  };

  const handleDelete = async (name: string) => {
    if (!token) return;
    try {
      await api(`/api/v1/plugins/${name}`, {
        token,
        method: "DELETE",
      });
      setDeleteConfirm(null);
      fetchPlugins();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Plugins</h1>
        <p className="text-muted-foreground">Upload, manage, and configure plugins</p>
      </div>

      {/* Upload zone */}
      <Card>
        <CardContent className="pt-6">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
              dragOver
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25"
            }`}
          >
            <p className="mb-2 text-sm text-muted-foreground">
              {uploading
                ? "Uploading..."
                : "Drag & drop a plugin .zip file here, or click to browse"}
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              onChange={handleFileChange}
              className="hidden"
            />
            <Button
              variant="outline"
              size="sm"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              Choose File
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Plugin list */}
      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : plugins.length === 0 ? (
        <p className="text-muted-foreground">No plugins installed.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {plugins.map((p) => (
            <Card key={p.name}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{p.name}</CardTitle>
                  <Badge variant={p.enabled !== false ? "default" : "secondary"}>
                    {p.enabled !== false ? "active" : "disabled"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">{p.description}</p>
                <div className="flex gap-2">
                  <Badge variant="outline">{p.engine}</Badge>
                  <Badge variant="outline">{p.category}</Badge>
                  <Badge variant="outline">v{p.version}</Badge>
                </div>
                <div className="flex items-center justify-between border-t pt-3">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={p.enabled !== false}
                      onCheckedChange={(checked) =>
                        handleToggle(p.name, checked)
                      }
                    />
                    <span className="text-sm text-muted-foreground">
                      {p.enabled !== false ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                  {deleteConfirm === p.name ? (
                    <div className="flex gap-1">
                      <Button
                        variant="destructive"
                        size="xs"
                        onClick={() => handleDelete(p.name)}
                      >
                        Confirm
                      </Button>
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => setDeleteConfirm(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeleteConfirm(p.name)}
                      className="text-destructive hover:text-destructive"
                    >
                      Delete
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
