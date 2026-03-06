"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiUpload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { PluginMeta, UpdateCheckResponse } from "@/types";
import { useTranslations } from "@/i18n/use-translations";

export default function PluginsPage() {
  const token = useAuth((s) => s.token);
  const { t } = useTranslations("plugins");
  const { t: tc } = useTranslations("common");
  const [plugins, setPlugins] = useState<PluginMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [updates, setUpdates] = useState<UpdateCheckResponse | null>(null);
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  const [updatingPlugin, setUpdatingPlugin] = useState<string | null>(null);
  const [updatingAll, setUpdatingAll] = useState(false);
  const [updateDialog, setUpdateDialog] = useState(false);
  const [updateMessage, setUpdateMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPlugins = useCallback(() => {
    if (!token) {
      setPlugins([]);
      setLoading(false);
      return;
    }
    api<PluginMeta[]>("/api/v1/plugins", { token })
      .then(setPlugins)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  const checkUpdates = useCallback(async () => {
    if (!token) return;
    setCheckingUpdates(true);
    try {
      const data = await api<UpdateCheckResponse>("/api/v1/marketplace/updates", { token });
      setUpdates(data);
    } catch (err) {
      console.error("Failed to check updates:", err);
    } finally {
      setCheckingUpdates(false);
    }
  }, [token]);

  useEffect(() => {
    fetchPlugins();
    checkUpdates();
  }, [fetchPlugins, checkUpdates]);

  const handleUpload = async (file: File) => {
    if (!token || !file.name.endsWith(".zip")) return;
    setUploading(true);
    try {
      await apiUpload("/api/v1/plugins/upload", file, token);
      fetchPlugins();
    } catch (e) {
      alert(e instanceof Error ? e.message : t("uploadFailed"));
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
      await api(`/api/v1/plugins/${encodeURIComponent(name)}`, {
        token,
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      });
      fetchPlugins();
    } catch (e) {
      alert(e instanceof Error ? e.message : t("toggleFailed"));
    }
  };

  const handleDelete = async (name: string) => {
    if (!token) return;
    try {
      await api(`/api/v1/plugins/${encodeURIComponent(name)}`, {
        token,
        method: "DELETE",
      });
      setDeleteConfirm(null);
      fetchPlugins();
    } catch (e) {
      alert(e instanceof Error ? e.message : t("deleteFailed"));
    }
  };

  const handleUpdatePlugin = async (name: string) => {
    if (!token) return;
    setUpdatingPlugin(name);
    try {
      const result = await api<{ success: boolean; message: string; version: string }>(
        `/api/v1/marketplace/update/${encodeURIComponent(name)}`,
        { token, method: "POST" }
      );
      setUpdateMessage(result.message);
      setUpdateDialog(true);
      fetchPlugins();
      checkUpdates();
    } catch (e) {
      alert(e instanceof Error ? e.message : t("updateFailed"));
    } finally {
      setUpdatingPlugin(null);
    }
  };

  const handleUpdateAll = async () => {
    if (!token) return;
    setUpdatingAll(true);
    try {
      const result = await api<{ success: boolean; message: string; updated: unknown[]; failed: unknown[] }>(
        "/api/v1/marketplace/update-all",
        { token, method: "POST" }
      );
      setUpdateMessage(result.message);
      setUpdateDialog(true);
      fetchPlugins();
      checkUpdates();
    } catch (e) {
      alert(e instanceof Error ? e.message : t("updateFailed"));
    } finally {
      setUpdatingAll(false);
    }
  };

  const getUpdateInfo = (pluginName: string) => {
    return updates?.plugins.find((u) => u.plugin_name === pluginName);
  };

  return (
    <div className="space-y-6">
      {/* Update Dialog */}
      <Dialog open={updateDialog} onOpenChange={setUpdateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("updateSuccess")}</DialogTitle>
            <DialogDescription>{updateMessage}</DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={checkUpdates}
            disabled={checkingUpdates}
          >
            {checkingUpdates ? t("checkingUpdates") : t("checkUpdates")}
          </Button>
          {updates && updates.updates_available > 0 && (
            <Button
              onClick={handleUpdateAll}
              disabled={updatingAll}
            >
              {updatingAll ? t("updating") : t("updateAll")} ({updates.updates_available})
            </Button>
          )}
        </div>
      </div>

      {updates && updates.updates_available > 0 && (
        <Card className="bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800">
          <CardContent className="pt-6">
            <p className="text-sm text-blue-900 dark:text-blue-100">
              {t("updatesAvailable", { count: updates.updates_available })}
            </p>
          </CardContent>
        </Card>
      )}

      {updates && updates.updates_available === 0 && !checkingUpdates && (
        <Card className="bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800">
          <CardContent className="pt-6">
            <p className="text-sm text-green-900 dark:text-green-100">
              {t("noUpdates")}
            </p>
          </CardContent>
        </Card>
      )}

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
              {uploading ? t("uploading") : t("uploadHint")}
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
              {t("chooseFile")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Plugin list */}
      {loading ? (
        <p className="text-muted-foreground">{tc("loading")}</p>
      ) : plugins.length === 0 ? (
        <p className="text-muted-foreground">{t("noPluginsInstalled")}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {plugins.map((p) => {
            const updateInfo = getUpdateInfo(p.name);
            return (
            <Card key={p.name}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{p.name}</CardTitle>
                  <div className="flex gap-1">
                    <Badge variant={p.enabled !== false ? "default" : "secondary"}>
                      {p.enabled !== false ? t("active") : t("disabled")}
                    </Badge>
                    {updateInfo && (
                      <Badge variant="secondary" className="bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-100">
                        {t("updateAvailable", { version: updateInfo.latest_version })}
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">{p.description}</p>
                <div className="flex gap-2">
                  <Badge variant="outline">{p.engine}</Badge>
                  <Badge variant="outline">{p.category}</Badge>
                  <Badge variant="outline">v{p.version}</Badge>
                </div>
                {updateInfo && updateInfo.has_breaking_changes && (
                  <p className="text-xs text-orange-600 dark:text-orange-400">
                    ⚠️ {t("breakingChanges")}
                  </p>
                )}
                <div className="flex items-center justify-between border-t pt-3">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={p.enabled !== false}
                      onCheckedChange={(checked) =>
                        handleToggle(p.name, checked)
                      }
                    />
                    <span className="text-sm text-muted-foreground">
                      {p.enabled !== false ? t("enabled") : t("disabledLabel")}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    {updateInfo && (
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => handleUpdatePlugin(p.name)}
                        disabled={updatingPlugin === p.name}
                      >
                        {updatingPlugin === p.name ? t("updating") : t("update")}
                      </Button>
                    )}
                    {deleteConfirm === p.name ? (
                      <>
                        <Button
                          variant="destructive"
                          size="xs"
                          onClick={() => handleDelete(p.name)}
                        >
                          {t("confirm")}
                        </Button>
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={() => setDeleteConfirm(null)}
                        >
                          {t("cancel")}
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteConfirm(p.name)}
                        className="text-destructive hover:text-destructive"
                      >
                        {t("delete")}
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )})}
        </div>
      )}
    </div>
  );
}
