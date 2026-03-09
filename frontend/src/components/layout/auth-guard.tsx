"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useAuth((s) => s.token);
  const user = useAuth((s) => s.user);
  const hydrated = useAuth((s) => s._hydrated);

  useEffect(() => {
    if (hydrated && !token) {
      router.replace("/login");
    } else if (hydrated && token && user && !user.terms_accepted_at) {
      router.replace("/terms");
    }
  }, [token, user, hydrated, router]);

  if (!hydrated || !token) return null;

  return <>{children}</>;
}
