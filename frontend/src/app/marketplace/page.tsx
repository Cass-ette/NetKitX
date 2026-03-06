"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Download, Star, Search, CheckCircle, Upload, Loader2 } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";

interface MarketplacePlugin {
  id: number;
  name: string;
  display_name: string;
  author: string;
  description: string;
  category: string;
  tags: string[];
  downloads: number;
  rating: number | null;
  verified: boolean;
}

export default function MarketplacePage() {
  const token = useAuth((s) => s.token);
  const { t } = useTranslations("marketplace");
  const [plugins, setPlugins] = useState<MarketplacePlugin[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  // Publish dialog
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishFile, setPublishFile] = useState<File | null>(null);
  const [publishLoading, setPublishLoading] = useState(false);
  const [publishResult, setPublishResult] = useState<{ ok: boolean; message: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadCategories();
    loadPlugins();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, searchQuery, selectedCategory, verifiedOnly]);

  const loadCategories = async () => {
    try {
      const data = await api<string[]>("/api/v1/marketplace/categories", { token: token || undefined });
      setCategories(data);
    } catch (error) {
      console.error("Failed to load categories:", error);
    }
  };

  const loadPlugins = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append("query", searchQuery);
      if (selectedCategory) params.append("category", selectedCategory);
      if (verifiedOnly) params.append("verified_only", "true");

      const data = await api<MarketplacePlugin[]>(
        `/api/v1/marketplace/plugins?${params}`,
        { token: token || undefined }
      );
      setPlugins(data);
    } catch (error) {
      console.error("Failed to load plugins:", error);
      setPlugins([]);
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async () => {
    if (!publishFile || !token) return;
    setPublishLoading(true);
    setPublishResult(null);
    try {
      const form = new FormData();
      form.append("file", publishFile);
      const res = await fetch(`${API_BASE}/api/v1/marketplace/publish`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const data = await res.json();
      if (res.ok) {
        setPublishResult({ ok: true, message: data.message || "Published successfully" });
        loadPlugins();
      } else {
        setPublishResult({ ok: false, message: data.detail || "Publish failed" });
      }
    } catch (e) {
      setPublishResult({ ok: false, message: String(e) });
    } finally {
      setPublishLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex gap-2">
          {token && (
            <Button
              onClick={() => {
                setPublishOpen(true);
                setPublishFile(null);
                setPublishResult(null);
              }}
            >
              <Upload className="mr-2 h-4 w-4" />
              发布插件
            </Button>
          )}
          <Link href="/plugins">
            <Button variant="outline">{t("myPlugins")}</Button>
          </Link>
        </div>
      </div>

      {/* Publish Dialog */}
      <Dialog open={publishOpen} onOpenChange={setPublishOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>发布插件</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm text-muted-foreground">
              上传包含 <code>plugin.yaml</code> 和 <code>main.py</code> 的 zip 压缩包。
            </p>
            <div
              className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
              {publishFile ? (
                <p className="text-sm font-medium">{publishFile.name}</p>
              ) : (
                <p className="text-sm text-muted-foreground">点击选择 zip 文件</p>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                className="hidden"
                onChange={(e) => setPublishFile(e.target.files?.[0] ?? null)}
              />
            </div>
            {publishResult && (
              <p className={`text-sm ${publishResult.ok ? "text-green-500" : "text-destructive"}`}>
                {publishResult.message}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPublishOpen(false)}>
              取消
            </Button>
            <Button onClick={handlePublish} disabled={!publishFile || publishLoading}>
              {publishLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              发布
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t("searchPlugins")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={selectedCategory || "all"}
              onValueChange={(value) => setSelectedCategory(value === "all" ? "" : value)}
            >
              <SelectTrigger className="w-48">
                <SelectValue placeholder={t("allCategories")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("allCategories")}</SelectItem>
                {categories.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant={verifiedOnly ? "default" : "outline"}
              onClick={() => setVerifiedOnly(!verifiedOnly)}
            >
              <CheckCircle className="mr-2 h-4 w-4" />
              {t("verifiedOnly")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Plugin Grid */}
      {loading ? (
        <div className="text-center py-12">{t("loadingPlugins")}</div>
      ) : plugins.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            {t("noPluginsFound")}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plugins.map((plugin) => (
            <Link key={plugin.id} href={`/marketplace/${plugin.name}`}>
              <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="flex items-center gap-2">
                        {plugin.display_name}
                        {plugin.verified && (
                          <CheckCircle className="h-4 w-4 text-blue-500" />
                        )}
                      </CardTitle>
                      <p className="text-sm text-muted-foreground mt-1">
                        {t("by", { author: plugin.author })}
                      </p>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm line-clamp-2">{plugin.description}</p>
                  <div className="flex flex-wrap gap-1">
                    {plugin.category && (
                      <Badge variant="secondary">{plugin.category}</Badge>
                    )}
                    {plugin.tags?.slice(0, 2).map((tag) => (
                      <Badge key={tag} variant="outline">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Download className="h-4 w-4" />
                      {plugin.downloads.toLocaleString()}
                    </div>
                    {plugin.rating && (
                      <div className="flex items-center gap-1">
                        <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                        {plugin.rating.toFixed(1)}
                      </div>
                    )}
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
