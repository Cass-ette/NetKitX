import { AppShell } from "@/components/layout/app-shell";

export default function TasksLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
