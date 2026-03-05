"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useTranslations } from "@/i18n/use-translations";

export default function SettingsPage() {
  const { t } = useTranslations("settings");

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
