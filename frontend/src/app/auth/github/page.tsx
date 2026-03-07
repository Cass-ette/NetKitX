"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";
import type { User } from "@/types";

function GitHubCallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setAuth } = useAuth();

  useEffect(() => {
    const token = searchParams.get("token");

    if (token) {
      api<User>("/api/v1/auth/me", { token })
        .then((user) => {
          setAuth(token, user);
          router.replace("/dashboard");
        })
        .catch(() => {
          router.replace("/login");
        });
    } else {
      router.replace("/login");
    }
  }, [searchParams, setAuth, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}

export default function GitHubCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <GitHubCallbackInner />
    </Suspense>
  );
}
