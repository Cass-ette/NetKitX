"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, Github, Fingerprint } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { API_BASE } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { login, register, setAuth } = useAuth();
  const { t } = useTranslations("login");
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [passkeySupported, setPasskeySupported] = useState(false);

  useEffect(() => {
    setPasskeySupported(
      typeof window !== "undefined" &&
      window.PublicKeyCredential !== undefined &&
      typeof window.PublicKeyCredential === "function"
    );
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isRegister) {
        await register(username, email, password);
      } else {
        await login(username, password);
      }
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("somethingWentWrong"));
    } finally {
      setLoading(false);
    }
  };

  const handlePasskeyLogin = async () => {
    if (!passkeySupported) {
      setError(t("passkeyNotSupported"));
      return;
    }
    setError("");
    setLoading(true);
    try {
      // Begin authentication
      const beginRes = await fetch(`${API_BASE}/api/v1/auth/passkey/login/begin`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!beginRes.ok) throw new Error("Failed to begin passkey login");
      const options = await beginRes.json();

      // Convert challenge from base64url to Uint8Array
      const challenge = Uint8Array.from(
        atob(options.challenge.replace(/-/g, "+").replace(/_/g, "/")),
        (c) => c.charCodeAt(0)
      );

      // Convert allowCredentials
      const allowCredentials = options.allowCredentials?.map((cred: { id: string; type: string; transports?: string[] }) => ({
        id: Uint8Array.from(
          atob(cred.id.replace(/-/g, "+").replace(/_/g, "/")),
          (c) => c.charCodeAt(0)
        ),
        type: cred.type,
        transports: cred.transports,
      }));

      // Get credential from authenticator
      const credential = await navigator.credentials.get({
        publicKey: {
          challenge,
          allowCredentials,
          rpId: options.rpId,
          userVerification: options.userVerification,
          timeout: options.timeout,
        },
      }) as PublicKeyCredential;

      if (!credential) throw new Error("No credential returned");

      // Prepare credential data for server
      const response = credential.response as AuthenticatorAssertionResponse;

      // Helper to convert ArrayBuffer to base64url
      const bufferToBase64url = (buffer: ArrayBuffer) => {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
      };

      const credentialData = {
        id: credential.id,
        rawId: credential.id,  // id is already base64url
        type: credential.type,
        response: {
          clientDataJSON: bufferToBase64url(response.clientDataJSON),
          authenticatorData: bufferToBase64url(response.authenticatorData),
          signature: bufferToBase64url(response.signature),
          userHandle: response.userHandle ? bufferToBase64url(response.userHandle) : null,
        },
      };

      // Complete authentication
      const completeRes = await fetch(`${API_BASE}/api/v1/auth/passkey/login/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: credentialData }),
      });
      if (!completeRes.ok) throw new Error("Failed to complete passkey login");
      const { access_token } = await completeRes.json();

      // Get user info
      const userRes = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      if (!userRes.ok) throw new Error("Failed to get user info");
      const user = await userRes.json();

      // Update auth store
      setAuth(access_token, user);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("somethingWentWrong"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">
            {isRegister ? t("createAccountTitle") : t("signInTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">{t("username")}</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            {isRegister && (
              <div className="space-y-2">
                <Label htmlFor="email">{t("email")}</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="password">{t("password")}</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? t("loading") : isRegister ? t("register") : t("signIn")}
            </Button>
          </form>
          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground">OR</span>
            </div>
          </div>
          <Button
            variant="outline"
            className="w-full"
            onClick={() => { window.location.href = `${API_BASE}/api/v1/auth/github`; }}
          >
            <Github className="mr-2 h-4 w-4" />
            GitHub
          </Button>
          {passkeySupported && (
            <Button
              variant="outline"
              className="w-full"
              onClick={handlePasskeyLogin}
              disabled={loading}
            >
              <Fingerprint className="mr-2 h-4 w-4" />
              {t("signInWithPasskey")}
            </Button>
          )}
          <div className="mt-4 text-center text-sm text-muted-foreground">
            {isRegister ? t("alreadyHaveAccount") : t("dontHaveAccount")}{" "}
            <button
              onClick={() => { setIsRegister(!isRegister); setError(""); }}
              className="text-primary underline-offset-4 hover:underline"
            >
              {isRegister ? t("signInLink") : t("registerLink")}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
