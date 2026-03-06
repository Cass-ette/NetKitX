import { AppShell } from "@/components/layout/app-shell";

export default function AIChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
