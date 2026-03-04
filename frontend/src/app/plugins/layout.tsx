import { AppShell } from "@/components/layout/app-shell";

export default function PluginsLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
