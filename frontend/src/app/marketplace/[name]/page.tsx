"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Download, Star, CheckCircle, ArrowLeft, Package } from "lucide-react";

interface PluginVersion {
  id: number;
  version: string;
  changelog: string | null;
  published_at: string;
  yanked: boolean;
}

interface PluginDetail {
  id: number;
  name: string;
  display_name: string;
  author: string;
  description: string;
  category: string;
  tags: string[];
  homepage_url: string | null;
  repository_url: string | null;
  license: string | null;
  downloads: number;
  rating: number | null;
  verified: boolean;
  versions: PluginVersion[];
  latest_version: string | null;
}

export default function PluginDetailPage() {
  const params = useParams();
  const router = useRouter();
  const token = useAuth((s) => s.token);
  const pluginName = params.name as string;

  const [plugin, setPlugin] = useState<PluginDetail | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<string | undefined>(undefined);
  const [installing, setInstalling] = useState(false);
  const [installSuccess, setInstallSuccess] = useState(false);
  const [installedPlugins, setInstalledPlugins] = useState<Array<{plugin: string, version: string}>>([]);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (pluginName) {
      loadPlugin();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pluginName, token]);

  const loadPlugin = async () => {
    try {
      const data = await api<PluginDetail>(
        `/api/v1/marketplace/plugins/${pluginName}`,
        { token: token || undefined }
      );
      setPlugin(data);
      setSelectedVersion(data.latest_version || data.versions.find(v => !v.yanked)?.version);
    } catch (error) {
      console.error("Failed to load plugin:", error);
      setError("Plugin not found");
    }
  };

  const handleInstall = async () => {
    if (!token) {
      router.push("/login");
      return;
    }

    setInstalling(true);
    setError("");
    setInstallSuccess(false);

    try {
      const result = await api<{success: boolean, installed: Array<{plugin: string, version: string}>}>(
        "/api/v1/marketplace/install",
        {
          token: token || undefined,
          method: "POST",
          body: JSON.stringify({
            plugin_name: pluginName,
            version: selectedVersion || undefined,
          }),
        }
      );

      setInstalledPlugins(result.installed);
      setInstallSuccess(true);
    } catch (err) {
      setError((err as Error).message || "Installation failed");
    } finally {
      setInstalling(false);
    }
  };

  if (error && !plugin) {
    return (
      <div className="container mx-auto p-6">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">{error}</p>
            <Button className="mt-4" onClick={() => router.push("/marketplace")}>
              Back to Marketplace
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!plugin) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">Loading...</div>
      </div>
    );
  }

  return (
    <>
      {/* Installation Progress Modal */}
      <Dialog open={installing || installSuccess} onOpenChange={(open) => {
        if (!open && installSuccess) {
          router.push("/plugins");
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {installing ? "Installing Plugin" : "Installation Complete"}
            </DialogTitle>
            <DialogDescription>
              {installing ? "Please wait while we install the plugin and its dependencies..." : "Plugin installed successfully!"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {installing && (
              <div className="flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            )}
            {installSuccess && installedPlugins.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Installed plugins:</p>
                {installedPlugins.map((p, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span>{p.plugin}</span>
                    <Badge variant="secondary">{p.version}</Badge>
                  </div>
                ))}
                <Button className="w-full mt-4" onClick={() => router.push("/plugins")}>
                  Go to My Plugins
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <div className="container mx-auto p-6 space-y-6">
      <Button variant="ghost" onClick={() => router.push("/marketplace")}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Marketplace
      </Button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-3xl flex items-center gap-2">
                    {plugin.display_name}
                    {plugin.verified && (
                      <CheckCircle className="h-6 w-6 text-blue-500" />
                    )}
                  </CardTitle>
                  <p className="text-muted-foreground mt-2">by {plugin.author}</p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-lg">{plugin.description}</p>

              <div className="flex flex-wrap gap-2">
                {plugin.category && (
                  <Badge variant="secondary">{plugin.category}</Badge>
                )}
                {plugin.tags?.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </div>

              <div className="flex items-center gap-6 text-sm text-muted-foreground">
                <div className="flex items-center gap-1">
                  <Download className="h-4 w-4" />
                  {plugin.downloads.toLocaleString()} downloads
                </div>
                {plugin.rating && (
                  <div className="flex items-center gap-1">
                    <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                    {plugin.rating.toFixed(1)} rating
                  </div>
                )}
                {plugin.license && (
                  <div className="flex items-center gap-1">
                    <Package className="h-4 w-4" />
                    {plugin.license}
                  </div>
                )}
              </div>

              {(plugin.homepage_url || plugin.repository_url) && (
                <div className="flex gap-4">
                  {plugin.homepage_url && (
                    <a
                      href={plugin.homepage_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-500 hover:underline"
                    >
                      Homepage
                    </a>
                  )}
                  {plugin.repository_url && (
                    <a
                      href={plugin.repository_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-500 hover:underline"
                    >
                      Repository
                    </a>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Versions */}
          <Card>
            <CardHeader>
              <CardTitle>Versions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {plugin.versions
                  .filter((v) => !v.yanked)
                  .map((version) => (
                    <div key={version.id} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge>{version.version}</Badge>
                          {version.version === plugin.latest_version && (
                            <Badge variant="secondary">Latest</Badge>
                          )}
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {new Date(version.published_at).toLocaleDateString()}
                        </span>
                      </div>
                      {version.changelog && (
                        <p className="text-sm text-muted-foreground">
                          {version.changelog}
                        </p>
                      )}
                      <Separator />
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Install</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Version</label>
                <Select value={selectedVersion || undefined} onValueChange={setSelectedVersion}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select version" />
                  </SelectTrigger>
                  <SelectContent>
                    {plugin.versions
                      .filter((v) => !v.yanked)
                      .map((v) => (
                        <SelectItem key={v.id} value={v.version}>
                          {v.version}
                          {v.version === plugin.latest_version && " (Latest)"}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              <Button
                className="w-full"
                onClick={handleInstall}
                disabled={installing || !selectedVersion}
              >
                {installing ? "Installing..." : "Install Plugin"}
              </Button>

              {error && (
                <p className="text-sm text-red-500">{error}</p>
              )}

              <p className="text-xs text-muted-foreground">
                This will install the plugin and all its dependencies.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
      </div>
    </>
  );
}
