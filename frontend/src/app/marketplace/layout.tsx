import { AppShell } from "@/components/layout/app-shell";

export default function MarketplaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
