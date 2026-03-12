import { AppShell } from "@/components/layout/app-shell";

export default function WorkflowsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
