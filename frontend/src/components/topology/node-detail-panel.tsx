"use client";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { useTranslations } from "@/i18n/use-translations";

interface NodeData {
  id: string;
  type: string;
  label: string;
  data: Record<string, unknown>;
}

interface NodeDetailPanelProps {
  node: NodeData | null;
  onClose: () => void;
}

export function NodeDetailPanel({ node, onClose }: NodeDetailPanelProps) {
  const { t } = useTranslations("topology");

  if (!node) return null;

  const ports = (node.data.ports as number[]) || [];
  const services = (node.data.services as string[]) || [];
  const host = (node.data.host as string) || node.label;

  return (
    <Sheet open={!!node} onOpenChange={(open) => !open && onClose()}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>{node.label}</SheetTitle>
        </SheetHeader>
        <div className="mt-6 space-y-4">
          <div>
            <h4 className="text-sm font-medium text-muted-foreground mb-1">{t("type")}</h4>
            <Badge>{node.type}</Badge>
          </div>

          {node.type === "host" && (
            <>
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1">{t("host")}</h4>
                <p className="font-mono text-sm">{host}</p>
              </div>

              {ports.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">
                    {t("openPorts", { count: ports.length })}
                  </h4>
                  <div className="flex flex-wrap gap-1">
                    {ports.map((port) => (
                      <Badge key={port} variant="outline">
                        {port}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {services.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">
                    {t("services", { count: services.length })}
                  </h4>
                  <div className="flex flex-wrap gap-1">
                    {services.map((svc) => (
                      <Badge key={svc} variant="secondary">
                        {svc}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {node.type === "scanner" && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-1">{t("totalResults")}</h4>
              <p className="text-2xl font-bold">
                {(node.data.total_results as number) || 0}
              </p>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
