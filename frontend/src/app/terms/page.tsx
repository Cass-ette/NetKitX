"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, Shield } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { User } from "@/types";

export default function TermsPage() {
  const { t } = useTranslations("settings");
  const router = useRouter();
  const token = useAuth((s) => s.token);
  const setAuth = useAuth((s) => s.setAuth);
  const [locale, setLocale] = useState("en");
  const [termsContent, setTermsContent] = useState("");
  const [checked, setChecked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("locale") || "en";
      setLocale(stored);
    }
  }, []);

  useEffect(() => {
    const loadTerms = async () => {
      try {
        const data = await api<{ version: string; content: string }>(`/api/v1/auth/terms?lang=${locale}`);
        setTermsContent(data.content);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load terms");
      }
    };
    loadTerms();
  }, [locale]);

  const handleAccept = async () => {
    if (!token || !checked) return;
    setLoading(true);
    setError(null);
    try {
      const user = await api<User>("/api/v1/auth/accept-terms", { method: "POST", token });
      setAuth(token, user);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept terms");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-3xl">
        <CardHeader>
          <div className="flex items-center gap-3">
            <Shield className="h-8 w-8 text-primary" />
            <div>
              <CardTitle className="text-2xl">{t("termsTitle")}</CardTitle>
              <CardDescription>{t("termsDesc")}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-h-96 overflow-y-auto rounded-md border p-4 bg-muted/30">
            <pre className="whitespace-pre-wrap text-sm font-mono">{termsContent}</pre>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox id="terms" checked={checked} onCheckedChange={(c) => setChecked(!!c)} />
            <label
              htmlFor="terms"
              className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
            >
              {t("termsCheckbox")}
            </label>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button onClick={handleAccept} disabled={!checked || loading} className="w-full">
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t("termsAccepting")}
              </>
            ) : (
              t("termsAccept")
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
