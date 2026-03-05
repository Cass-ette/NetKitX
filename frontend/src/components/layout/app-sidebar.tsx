"use client";

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
} from "@/components/ui/sidebar";
import { useTranslations } from "@/i18n/use-translations";
import type { LucideIcon } from "lucide-react";

const navItems: { key: string; href: string; icon: LucideIcon }[] = [
  { key: "dashboard", href: "/dashboard", icon: LayoutDashboard },
  { key: "tools", href: "/tools", icon: Wrench },
  { key: "tasks", href: "/tasks", icon: ListTodo },
  { key: "plugins", href: "/plugins", icon: Puzzle },
  { key: "marketplace", href: "/marketplace", icon: Store },
  { key: "topology", href: "/topology", icon: Network },
  { key: "aiChat", href: "/ai-chat", icon: Bot },
  { key: "settings", href: "/settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { t } = useTranslations("common");

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
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton asChild isActive={pathname.startsWith(item.href)}>
                    <Link href={item.href}>
                      <item.icon className="h-4 w-4" />
                      <span>{t(item.key)}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
