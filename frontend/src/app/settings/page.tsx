"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Save, Trash2, Fingerprint, Plus, Shield } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { AISettings, AuthorizedTarget } from "@/types";

interface PasskeyCredential {
  id: number;
  name: string | null;
  created_at: string;
  last_used_at: string | null;
  transports: string[] | null;
}

interface PasskeyRegistrationOptions {
  challenge: string;
  rp: { id: string; name: string };
  user: { id: string; name: string; displayName: string };
  pubKeyCredParams: Array<{ type: "public-key"; alg: number }>;
  authenticatorSelection: Record<string, unknown>;
  timeout: number;
  excludeCredentials?: Array<{ id: string; type: string }>;
}

export default function SettingsPage() {
  const { t } = useTranslations("settings");
  const token = useAuth((s) => s.token);

  const [aiProvider, setAiProvider] = useState("claude");
  const [aiApiKey, setAiApiKey] = useState("");
  const [aiModel, setAiModel] = useState("claude-sonnet-4-20250514");
  const [aiBaseUrl, setAiBaseUrl] = useState("");
  const [aiConfigured, setAiConfigured] = useState(false);
  const [aiMasked, setAiMasked] = useState("");
  const [aiSaving, setAiSaving] = useState(false);
  const [aiMsg, setAiMsg] = useState<string | null>(null);

  const [passkeys, setPasskeys] = useState<PasskeyCredential[]>([]);
  const [passkeySupported, setPasskeySupported] = useState(false);
  const [passkeyLoading, setPasskeyLoading] = useState(false);
  const [passkeyMsg, setPasskeyMsg] = useState<string | null>(null);

  const [whitelist, setWhitelist] = useState<AuthorizedTarget[]>([]);
  const [whitelistType, setWhitelistType] = useState<"domain" | "ip" | "cidr">("domain");
  const [whitelistValue, setWhitelistValue] = useState("");
  const [whitelistNotes, setWhitelistNotes] = useState("");
  const [whitelistDeclaration, setWhitelistDeclaration] = useState(true);
  const [whitelistLoading, setWhitelistLoading] = useState(false);
  const [whitelistMsg, setWhitelistMsg] = useState<string | null>(null);

  const loadAiSettings = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api<AISettings>("/api/v1/ai/settings", { token });
      setAiProvider(data.provider);
      setAiModel(data.model);
      setAiBaseUrl(data.base_url || "");
      setAiMasked(data.api_key_masked);
      setAiConfigured(true);
    } catch {
      setAiConfigured(false);
    }
  }, [token]);

  const loadPasskeys = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api<PasskeyCredential[]>("/api/v1/auth/passkey/credentials", { token });
      setPasskeys(data);
    } catch {
      setPasskeys([]);
    }
  }, [token]);

  const loadWhitelist = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api<AuthorizedTarget[]>("/api/v1/whitelist", { token });
      setWhitelist(data);
    } catch {
      setWhitelist([]);
    }
  }, [token]);

  useEffect(() => {
    loadAiSettings();
    loadPasskeys();
    loadWhitelist();
    setPasskeySupported(
      typeof window !== "undefined" &&
      window.PublicKeyCredential !== undefined
    );
  }, [loadAiSettings, loadPasskeys, loadWhitelist]);

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
          base_url: aiBaseUrl || null,
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

  const handleAddPasskey = async () => {
    if (!token || !passkeySupported) return;
    setPasskeyLoading(true);
    setPasskeyMsg(null);
    try {
      // Begin registration
      const beginRes = await api<PasskeyRegistrationOptions>("/api/v1/auth/passkey/register/begin", {
        method: "POST",
        token,
        body: JSON.stringify({ name: null }),
      });

      // Convert challenge from base64url to Uint8Array
      const challenge = Uint8Array.from(
        atob(beginRes.challenge.replace(/-/g, "+").replace(/_/g, "/")),
        (c) => c.charCodeAt(0)
      );

      // Convert user.id
      const userId = Uint8Array.from(
        atob(beginRes.user.id.replace(/-/g, "+").replace(/_/g, "/")),
        (c) => c.charCodeAt(0)
      );

      // Convert excludeCredentials
      const excludeCredentials = beginRes.excludeCredentials?.map((cred: { id: string; type: string }) => ({
        id: Uint8Array.from(
          atob(cred.id.replace(/-/g, "+").replace(/_/g, "/")),
          (c) => c.charCodeAt(0)
        ),
        type: "public-key" as const,
      }));

      // Create credential
      const credential = await navigator.credentials.create({
        publicKey: {
          challenge,
          rp: beginRes.rp,
          user: {
            id: userId,
            name: beginRes.user.name,
            displayName: beginRes.user.displayName,
          },
          pubKeyCredParams: beginRes.pubKeyCredParams,
          authenticatorSelection: beginRes.authenticatorSelection,
          timeout: beginRes.timeout,
          excludeCredentials,
        },
      }) as PublicKeyCredential;

      if (!credential) throw new Error("No credential returned");

      // Prepare credential data for server
      const response = credential.response as AuthenticatorAttestationResponse;

      // Helper to convert ArrayBuffer to base64url
      const bufferToBase64url = (buffer: ArrayBuffer) => {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
      };

      const credentialData = {
        id: credential.id,
        rawId: credential.id,  // id is already base64url
        type: credential.type,
        response: {
          clientDataJSON: bufferToBase64url(response.clientDataJSON),
          attestationObject: bufferToBase64url(response.attestationObject),
          transports: response.getTransports ? response.getTransports() : undefined,
        },
      };

      // Complete registration
      await api("/api/v1/auth/passkey/register/complete", {
        method: "POST",
        token,
        body: JSON.stringify({ credential: credentialData }),
      });

      setPasskeyMsg(t("passkeyAdded"));
      await loadPasskeys();
    } catch (err) {
      setPasskeyMsg(err instanceof Error ? err.message : "Error");
    } finally {
      setPasskeyLoading(false);
    }
  };

  const handleDeletePasskey = async (id: number) => {
    if (!token) return;
    setPasskeyLoading(true);
    setPasskeyMsg(null);
    try {
      await api(`/api/v1/auth/passkey/credentials/${id}`, { method: "DELETE", token });
      setPasskeyMsg(t("passkeyDeleted"));
      await loadPasskeys();
    } catch (err) {
      setPasskeyMsg(err instanceof Error ? err.message : "Error");
    } finally {
      setPasskeyLoading(false);
    }
  };

  const handleAddWhitelist = async () => {
    if (!token || !whitelistValue || !whitelistDeclaration) return;
    setWhitelistLoading(true);
    setWhitelistMsg(null);
    try {
      await api("/api/v1/whitelist", {
        method: "POST",
        token,
        body: JSON.stringify({
          target_type: whitelistType,
          target_value: whitelistValue,
          declaration: whitelistDeclaration,
          notes: whitelistNotes || null,
        }),
      });
      setWhitelistValue("");
      setWhitelistNotes("");
      setWhitelistMsg(t("whitelistAdded"));
      await loadWhitelist();
    } catch (err) {
      setWhitelistMsg(err instanceof Error ? err.message : "Error");
    } finally {
      setWhitelistLoading(false);
    }
  };

  const handleDeleteWhitelist = async (id: number) => {
    if (!token) return;
    setWhitelistLoading(true);
    setWhitelistMsg(null);
    try {
      await api(`/api/v1/whitelist/${id}`, { method: "DELETE", token });
      setWhitelistMsg(t("whitelistRemoved"));
      await loadWhitelist();
    } catch (err) {
      setWhitelistMsg(err instanceof Error ? err.message : "Error");
    } finally {
      setWhitelistLoading(false);
    }
  };

  const defaultModels: Record<string, string> = {
    claude: "claude-sonnet-4-20250514",
    deepseek: "deepseek-chat",
    glm: "glm-4-flash",
    custom: "",
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
              {aiBaseUrl && <p><strong>{t("aiBaseUrl")}:</strong> {aiBaseUrl}</p>}
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
                <SelectItem value="glm">GLM (智谱 AI)</SelectItem>
                <SelectItem value="custom">{t("aiCustom")}</SelectItem>
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

          <div className="space-y-2">
            <Label>{t("aiBaseUrl")}</Label>
            <Input
              placeholder={t("aiBaseUrlPlaceholder")}
              value={aiBaseUrl}
              onChange={(e) => setAiBaseUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t("aiBaseUrlHint")}</p>
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

      {/* Passkey Management Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Fingerprint className="h-5 w-5" />
                {t("passkeyTitle")}
              </CardTitle>
              <CardDescription>{t("passkeyDesc")}</CardDescription>
            </div>
            {passkeySupported && (
              <Button onClick={handleAddPasskey} disabled={passkeyLoading} size="sm">
                <Plus className="mr-2 h-4 w-4" />
                {t("passkeyAdd")}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!passkeySupported && (
            <p className="text-sm text-muted-foreground">{t("passkeyNotSupported")}</p>
          )}

          {passkeySupported && passkeys.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("passkeyNoCredentials")}</p>
          )}

          {passkeySupported && passkeys.length > 0 && (
            <div className="space-y-2">
              {passkeys.map((pk) => (
                <div key={pk.id} className="flex items-center justify-between rounded-md border p-3">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">
                      {pk.name || `Passkey #${pk.id}`}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("passkeyCreated")}: {new Date(pk.created_at).toLocaleDateString()}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("passkeyLastUsed")}: {pk.last_used_at ? new Date(pk.last_used_at).toLocaleDateString() : t("passkeyNever")}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeletePasskey(pk.id)}
                    disabled={passkeyLoading}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {passkeyMsg && (
            <p className="text-sm text-muted-foreground">{passkeyMsg}</p>
          )}
        </CardContent>
      </Card>

      {/* Authorized Targets Whitelist Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                {t("whitelistTitle")}
              </CardTitle>
              <CardDescription>{t("whitelistDesc")}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {whitelist.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("whitelistEmpty")}</p>
          )}

          {whitelist.length > 0 && (
            <div className="space-y-2">
              {whitelist.map((target) => (
                <div key={target.id} className="flex items-center justify-between rounded-md border p-3">
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{t(`whitelist${target.target_type.charAt(0).toUpperCase() + target.target_type.slice(1)}`)}</Badge>
                      <span className="text-sm font-medium">{target.target_value}</span>
                    </div>
                    {target.notes && (
                      <p className="text-xs text-muted-foreground">{target.notes}</p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteWhitelist(target.id)}
                    disabled={whitelistLoading}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className="space-y-3 rounded-md border p-4 bg-muted/30">
            <div className="space-y-2">
              <Label>{t("whitelistType")}</Label>
              <Select value={whitelistType} onValueChange={(v: "domain" | "ip" | "cidr") => setWhitelistType(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="domain">{t("whitelistDomain")}</SelectItem>
                  <SelectItem value="ip">{t("whitelistIp")}</SelectItem>
                  <SelectItem value="cidr">{t("whitelistCidr")}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>{t("whitelistValue")}</Label>
              <Input
                placeholder={whitelistType === "domain" ? "example.com" : whitelistType === "ip" ? "192.168.1.1" : "192.168.1.0/24"}
                value={whitelistValue}
                onChange={(e) => setWhitelistValue(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>{t("whitelistNotes")}</Label>
              <Textarea
                placeholder={t("whitelistNotesPlaceholder")}
                value={whitelistNotes}
                onChange={(e) => setWhitelistNotes(e.target.value)}
                rows={2}
              />
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="whitelist-declaration"
                checked={whitelistDeclaration}
                onCheckedChange={(c) => setWhitelistDeclaration(!!c)}
              />
              <label
                htmlFor="whitelist-declaration"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                {t("whitelistDeclaration")}
              </label>
            </div>

            {whitelistMsg && (
              <p className="text-sm text-muted-foreground">{whitelistMsg}</p>
            )}

            <Button
              onClick={handleAddWhitelist}
              disabled={whitelistLoading || !whitelistValue || !whitelistDeclaration}
              className="w-full"
            >
              {whitelistLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              {t("whitelistAdd")}
            </Button>
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
