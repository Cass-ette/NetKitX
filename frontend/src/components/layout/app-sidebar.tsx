"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Wrench,
  ListTodo,
  Puzzle,
  Settings,
  Shield,
  Store,
  Network,
  Bot,
  ShieldCheck,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarMenuBadge,
} from "@/components/ui/sidebar";
import { useTranslations } from "@/i18n/use-translations";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { LucideIcon } from "lucide-react";
import type { UpdateCheckResponse } from "@/types";

const navItems: { key: string; href: string; icon: LucideIcon; adminOnly?: boolean }[] = [
  { key: "dashboard", href: "/dashboard", icon: LayoutDashboard },
  { key: "tools", href: "/tools", icon: Wrench },
  { key: "tasks", href: "/tasks", icon: ListTodo },
  { key: "plugins", href: "/plugins", icon: Puzzle },
  { key: "marketplace", href: "/marketplace", icon: Store },
  { key: "topology", href: "/topology", icon: Network },
  { key: "aiChat", href: "/ai-chat", icon: Bot },
  { key: "admin", href: "/admin", icon: ShieldCheck, adminOnly: true },
  { key: "settings", href: "/settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { t } = useTranslations("common");
  const token = useAuth((s) => s.token);
  const user = useAuth((s) => s.user);
  const [updateCount, setUpdateCount] = useState(0);

  useEffect(() => {
    const checkUpdates = async () => {
      if (!token) return;
      try {
        const data = await api<UpdateCheckResponse>("/api/v1/marketplace/updates", { token });
        setUpdateCount(data.updates_available);
      } catch (err) {
        console.error("Failed to check updates:", err);
      }
    };

    checkUpdates();
    // Check every 5 minutes
    const interval = setInterval(checkUpdates, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [token]);

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3">
        <Link href="/dashboard" className="flex items-center gap-2 font-bold text-lg">
          <Shield className="h-6 w-6" />
          <span>NetKitX</span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("navigation")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems
                .filter((item) => !item.adminOnly || user?.role === "admin")
                .map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton asChild isActive={pathname.startsWith(item.href)}>
                    <Link href={item.href}>
                      <item.icon className="h-4 w-4" />
                      <span>{t(item.key)}</span>
                    </Link>
                  </SidebarMenuButton>
                  {item.key === "plugins" && updateCount > 0 && (
                    <SidebarMenuBadge>{updateCount}</SidebarMenuBadge>
                  )}
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
