"use client";

import { useEffect } from "react";
import { SidebarProvider, SidebarTrigger, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useAIChatStore } from "@/lib/ai-chat-store";
import { LogOut, Bot } from "lucide-react";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { AIChatPanel } from "@/components/ai/ai-chat-panel";
import { useTranslations } from "@/i18n/use-translations";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { togglePanel, panelOpen } = useAIChatStore();
  const { t } = useTranslations("ai");

  // Cmd+Shift+I / Ctrl+Shift+I shortcut to toggle panel
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "i") {
        e.preventDefault();
        togglePanel();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [togglePanel]);

  return (
    <AuthGuard>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset className="h-svh max-h-svh overflow-hidden">
          <header className="flex h-14 shrink-0 items-center justify-between border-b px-4">
            <div className="flex items-center gap-2">
              <SidebarTrigger />
              <Separator orientation="vertical" className="h-4" />
              <span className="text-sm text-muted-foreground">NetKitX</span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant={panelOpen ? "secondary" : "ghost"}
                size="icon"
                onClick={togglePanel}
                title={panelOpen ? t("closePanel") : t("openPanel")}
              >
                <Bot className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground">{user?.username}</span>
              <LanguageSwitcher />
              <Button variant="ghost" size="icon" onClick={logout}>
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </header>
          <div className="flex flex-1 overflow-hidden">
            <main className="flex-1 min-w-0 p-6 overflow-y-auto">{children}</main>
            <AIChatPanel />
          </div>
        </SidebarInset>
      </SidebarProvider>
    </AuthGuard>
  );
}
