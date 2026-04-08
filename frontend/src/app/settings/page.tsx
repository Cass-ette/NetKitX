"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Save, Trash2, Fingerprint, Plus } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { AISettings, ProviderConfig } from "@/types";

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

const defaultModels: Record<string, string> = {
  deepseek: "deepseek-chat",
  glm: "glm-4-flash",
  custom: "",
};


export default function SettingsPage() {
  const { t } = useTranslations("settings");
  const token = useAuth((s) => s.token);

  // Active provider selection
  const [activeProvider, setActiveProvider] = useState("deepseek");
  const [aiConfigured, setAiConfigured] = useState(false);
  const [aiSaving, setAiSaving] = useState(false);
  const [aiMsg, setAiMsg] = useState<string | null>(null);

  // Provider-specific configs
  const [configs, setConfigs] = useState<Record<string, ProviderConfig>>({
    deepseek: { api_key: "", api_key_masked: "", model: defaultModels.deepseek, base_url: null },
    glm: { api_key: "", api_key_masked: "", model: defaultModels.glm, base_url: null },
    custom: { api_key: "", api_key_masked: "", model: "", base_url: "" },
  });

  // Temp input state for API keys (not saved until click save)
  const [tempKeys, setTempKeys] = useState<Record<string, string>>({
    deepseek: "",
    glm: "",
    custom: "",
  });

  const [passkeys, setPasskeys] = useState<PasskeyCredential[]>([]);
  const [passkeySupported, setPasskeySupported] = useState(false);
  const [passkeyLoading, setPasskeyLoading] = useState(false);
  const [passkeyMsg, setPasskeyMsg] = useState<string | null>(null);

  const loadAiSettings = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api<AISettings>("/api/v1/ai/settings", { token });
      setActiveProvider(data.provider);
      setConfigs({
        deepseek: data.deepseek,
        glm: data.glm,
        custom: data.custom,
      });
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

  useEffect(() => {
    loadAiSettings();
    loadPasskeys();

    const checkPasskeySupport = async () => {
      if (typeof window === "undefined" || !window.PublicKeyCredential) {
        setPasskeySupported(false);
        return;
      }

      try {
        const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
        setPasskeySupported(available);
      } catch {
        setPasskeySupported(false);
      }
    };

    checkPasskeySupport();
  }, [loadAiSettings, loadPasskeys]);

  const handleAiSave = async () => {
    if (!token) return;
    setAiSaving(true);
    setAiMsg(null);
    try {
      await api("/api/v1/ai/settings", {
        method: "PUT",
        token,
        body: JSON.stringify({
          provider: activeProvider,
          deepseek: {
            api_key: tempKeys.deepseek,
            api_key_masked: configs.deepseek.api_key_masked,
            model: configs.deepseek.model,
            base_url: null,
          },
          glm: {
            api_key: tempKeys.glm,
            api_key_masked: configs.glm.api_key_masked,
            model: configs.glm.model,
            base_url: null,
          },
          custom: {
            api_key: tempKeys.custom,
            api_key_masked: configs.custom.api_key_masked,
            model: configs.custom.model,
            base_url: configs.custom.base_url,
          },
        }),
      });
      setTempKeys({ deepseek: "", glm: "", custom: "" });
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
      setConfigs({
        deepseek: { api_key: "", api_key_masked: "", model: defaultModels.deepseek, base_url: null },
        glm: { api_key: "", api_key_masked: "", model: defaultModels.glm, base_url: null },
        custom: { api_key: "", api_key_masked: "", model: "", base_url: "" },
      });
      setAiMsg(t("aiDeleted"));
    } catch (err) {
      setAiMsg(err instanceof Error ? err.message : "Error");
    } finally {
      setAiSaving(false);
    }
  };

  const updateConfig = (provider: string, field: keyof ProviderConfig, value: string | null) => {
    setConfigs((prev) => ({
      ...prev,
      [provider]: { ...prev[provider], [field]: value },
    }));
  };

  const renderProviderConfig = (provider: string) => {
    const config = configs[provider];
    const hasKey = config.api_key_masked && config.api_key_masked !== "";

    return (
      <div className="space-y-4">
        {hasKey && (
          <div className="rounded-md bg-muted p-3 text-sm">
            <p><strong>{t("aiApiKey")}:</strong> {config.api_key_masked}</p>
          </div>
        )}

        <div className="space-y-2">
          <Label>{t("aiApiKey")}</Label>
          <Input
            type="password"
            placeholder={hasKey ? "Enter new key to update..." : "sk-..."}
            value={tempKeys[provider]}
            onChange={(e) => setTempKeys((prev) => ({ ...prev, [provider]: e.target.value }))}
          />
        </div>

        <div className="space-y-2">
          <Label>{t("aiModel")}</Label>
          <Input
            placeholder={provider === "deepseek" ? "deepseek-chat" : provider === "glm" ? "glm-4-flash" : "model-name"}
            value={config.model}
            onChange={(e) => updateConfig(provider, "model", e.target.value)}
          />
        </div>

        {provider === "custom" && (
          <div className="space-y-2">
            <Label>{t("aiBaseUrl")}</Label>
            <Input
              placeholder={t("aiBaseUrlPlaceholder")}
              value={config.base_url || ""}
              onChange={(e) => updateConfig(provider, "base_url", e.target.value || null)}
            />
            <p className="text-xs text-muted-foreground">{t("aiBaseUrlHint")}</p>
          </div>
        )}
      </div>
    );
  };

  const handleAddPasskey = async () => {
    if (!token || !passkeySupported) return;
    setPasskeyLoading(true);
    setPasskeyMsg(null);
    try {
      const beginRes = await api<PasskeyRegistrationOptions>("/api/v1/auth/passkey/register/begin", {
        method: "POST",
        token,
        body: JSON.stringify({ name: null }),
      });

      const challenge = Uint8Array.from(
        atob(beginRes.challenge.replace(/-/g, "+").replace(/_/g, "/")),
        (c) => c.charCodeAt(0)
      );

      const userId = Uint8Array.from(
        atob(beginRes.user.id.replace(/-/g, "+").replace(/_/g, "/")),
        (c) => c.charCodeAt(0)
      );

      const excludeCredentials = beginRes.excludeCredentials?.map((cred: { id: string; type: string }) => ({
        id: Uint8Array.from(
          atob(cred.id.replace(/-/g, "+").replace(/_/g, "/")),
          (c) => c.charCodeAt(0)
        ),
        type: "public-key" as const,
      }));

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

      const response = credential.response as AuthenticatorAttestationResponse;

      const bufferToBase64url = (buffer: ArrayBuffer) => {
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
      };

      const credentialData = {
        id: credential.id,
        rawId: credential.id,
        type: credential.type,
        response: {
          clientDataJSON: bufferToBase64url(response.clientDataJSON),
          attestationObject: bufferToBase64url(response.attestationObject),
          transports: response.getTransports ? response.getTransports() : undefined,
        },
      };

      await api("/api/v1/auth/passkey/register/complete", {
        method: "POST",
        token,
        body: JSON.stringify({ credential: credentialData }),
      });

      setPasskeyMsg(t("passkeyAdded"));
      await loadPasskeys();
    } catch (err) {
      let errorMsg = "Error";
      if (err instanceof Error) {
        if (err.name === "NotAllowedError") {
          errorMsg = "Passkey registration was cancelled or timed out";
        } else if (err.name === "InvalidStateError") {
          errorMsg = "This passkey is already registered";
        } else if (err.name === "NotSupportedError") {
          errorMsg = "Passkey is not supported on this device";
        } else if (err.name === "SecurityError") {
          errorMsg = `Security error: ${err.message}`;
        } else if (err.name === "NotReadableError") {
          errorMsg = "Cannot access biometric sensor. Please check device permissions and configuration.";
        } else if (err.name === "UnknownError") {
          errorMsg = `Unknown error: ${err.message}`;
        } else {
          errorMsg = `${err.name}: ${err.message}`;
        }
      }
      setPasskeyMsg(errorMsg);
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

  // Check if any provider has a key to enable save
  const hasAnyKey = Object.values(tempKeys).some((k) => k.trim() !== "");

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
          {/* Active Provider Selection */}
          <div className="space-y-2">
            <Label>{t("aiProvider")} ({t("active")})</Label>
            <Select value={activeProvider} onValueChange={setActiveProvider}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="deepseek">DeepSeek</SelectItem>
                <SelectItem value="glm">GLM (智谱 AI)</SelectItem>
                <SelectItem value="custom">{t("aiCustom")}</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t("activeProviderHint") || "Select which provider to use for AI features"}
            </p>
          </div>

          {/* Provider-specific Tabs */}
          <Tabs defaultValue="deepseek" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="deepseek">DeepSeek</TabsTrigger>
              <TabsTrigger value="glm">GLM</TabsTrigger>
              <TabsTrigger value="custom">{t("aiCustom")}</TabsTrigger>
            </TabsList>
            <TabsContent value="deepseek" className="pt-4">
              {renderProviderConfig("deepseek")}
            </TabsContent>
            <TabsContent value="glm" className="pt-4">
              {renderProviderConfig("glm")}
            </TabsContent>
            <TabsContent value="custom" className="pt-4">
              {renderProviderConfig("custom")}
            </TabsContent>
          </Tabs>

          {aiMsg && <p className="text-sm text-muted-foreground">{aiMsg}</p>}

          <div className="flex gap-2">
            <Button onClick={handleAiSave} disabled={aiSaving || (!hasAnyKey && !aiConfigured)}>
              {aiSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
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
          {!passkeySupported && <p className="text-sm text-muted-foreground">{t("passkeyNotSupported")}</p>}

          {passkeySupported && passkeys.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("passkeyNoCredentials")}</p>
          )}

          {passkeySupported && passkeys.length > 0 && (
            <div className="space-y-2">
              {passkeys.map((pk) => (
                <div key={pk.id} className="flex items-center justify-between rounded-md border p-3">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{pk.name || `Passkey #${pk.id}`}</p>
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

          {passkeyMsg && <p className="text-sm text-muted-foreground">{passkeyMsg}</p>}
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
