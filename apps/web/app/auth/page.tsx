"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getApiBaseUrl } from "../../lib/dev-context";

type SessionPayload = {
  authenticated: boolean;
  session?: {
    user_id: string;
    org_id: string;
    role: string;
  } | null;
};

type AuthMode = "login" | "register" | "request-reset" | "confirm-reset";
type OrgOption = { org_id: string; org_name: string; role: string };

function getCookieValue(name: string): string {
  const prefix = `${name}=`;
  const parts = document.cookie.split("; ");
  for (const part of parts) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return "";
}

function setMirroredSessionCookie(payload: SessionPayload) {
  if (!payload.authenticated || !payload.session) {
    document.cookie = "omniflow_session_ctx=; Path=/; Max-Age=0; SameSite=Lax";
    return;
  }

  const raw = JSON.stringify({
    user_id: payload.session.user_id,
    org_id: payload.session.org_id,
    role: payload.session.role
  });
  const encoded = btoa(raw).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  document.cookie = `omniflow_session_ctx=${encoded}; Path=/; Max-Age=86400; SameSite=Lax`;
}

export default function AuthPage(): JSX.Element {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const routeMode = useMemo<AuthMode>(() => {
    if (pathname.endsWith("/create")) return "register";
    if (pathname.endsWith("/reset")) return "request-reset";
    return "login";
  }, [pathname]);
  const nextPath = searchParams.get("next") || "/dashboard";
  const apiBase = useMemo(() => getApiBaseUrl(), []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [orgId, setOrgId] = useState("");
  const [orgOptions, setOrgOptions] = useState<OrgOption[]>([]);
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [mode, setMode] = useState<AuthMode>(routeMode);
  const [message, setMessage] = useState("Sign in with your credential, or create one if you are new.");
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const lookupDebounceRef = useRef<number | null>(null);
  const lastOrgLookupRef = useRef<string>("");

  useEffect(() => {
    setMode(routeMode);
  }, [routeMode]);

  async function checkSession({ redirectOnSuccess = true }: { redirectOnSuccess?: boolean } = {}): Promise<SessionPayload | null> {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/auth/session`, { credentials: "include", cache: "no-store" });
      const payload = (await response.json()) as SessionPayload;
      setSession(payload);
      setMirroredSessionCookie(payload);
      setMessage(payload.authenticated ? "Session is active." : "No active session.");
      if (payload.authenticated && redirectOnSuccess) {
        window.location.assign(nextPath);
      }
      return payload;
    } catch {
      setMessage("Failed to check session.");
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("Creating session...");

    try {
      const response = await fetch(`${apiBase}/auth/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password: password || undefined, org_id: orgId || undefined }),
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setMessage(payload.detail ?? "Login failed.");
        return;
      }
      const verified = await checkSession({ redirectOnSuccess: false });
      if (verified?.authenticated) {
        setMessage("Session created. Redirecting...");
        window.location.assign(nextPath);
      } else {
        setMessage("Login succeeded, but no active session cookie was detected. Check cookie/CORS settings.");
      }
    } catch {
      setMessage("Login failed.");
    } finally {
      setLoading(false);
    }
  }

  const loadOrgOptions = useCallback(async ({ quiet = false }: { quiet?: boolean } = {}) => {
    if (!quiet) {
      setLoading(true);
      setMessage("Loading organizations...");
    }
    try {
      const response = await fetch(`${apiBase}/auth/org-options`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password: password || undefined }),
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setMessage(payload.detail ?? "Unable to load organizations.");
        return;
      }
      const payload = (await response.json()) as { items?: OrgOption[] };
      const items = payload.items ?? [];
      setOrgOptions(items);
      if (items.length > 0) {
        setOrgId(items[0].org_id);
      } else {
        setOrgId("");
      }
      if (!quiet) {
        setMessage(items.length > 0 ? "Select organization and sign in." : "No organizations found for this user.");
      }
    } catch {
      if (!quiet) {
        setMessage("Unable to load organizations.");
      }
    } finally {
      if (!quiet) {
        setLoading(false);
      }
    }
  }, [apiBase, email, password]);

  useEffect(() => {
    if (mode !== "login") {
      return;
    }
    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail || !password) {
      setOrgOptions([]);
      setOrgId("");
      lastOrgLookupRef.current = "";
      if (lookupDebounceRef.current !== null) {
        window.clearTimeout(lookupDebounceRef.current);
      }
      return;
    }

    const key = `${trimmedEmail}:${password}`;
    if (key === lastOrgLookupRef.current) {
      return;
    }

    if (lookupDebounceRef.current !== null) {
      window.clearTimeout(lookupDebounceRef.current);
    }
    lookupDebounceRef.current = window.setTimeout(() => {
      lastOrgLookupRef.current = key;
      void loadOrgOptions({ quiet: true });
    }, 500);

    return () => {
      if (lookupDebounceRef.current !== null) {
        window.clearTimeout(lookupDebounceRef.current);
      }
    };
  }, [email, loadOrgOptions, mode, password]);

  async function submitRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("Creating credential...");
    try {
      const response = await fetch(`${apiBase}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password, full_name: fullName || undefined, org_name: orgName || undefined }),
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setMessage(payload.detail ?? "Registration failed.");
        return;
      }
      setMessage("Credential created. You can now sign in.");
      setMode("login");
    } catch {
      setMessage("Registration failed.");
    } finally {
      setLoading(false);
    }
  }

  async function requestPasswordReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("Requesting reset token...");
    try {
      const response = await fetch(`${apiBase}/auth/password-reset/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email }),
      });
      const payload = (await response.json()) as { accepted?: boolean; reset_token_preview?: string | null };
      if (!response.ok) {
        setMessage("Failed to request password reset.");
        return;
      }
      if (payload.reset_token_preview) {
        setResetToken(payload.reset_token_preview);
        setMode("confirm-reset");
        setMessage("Reset token generated for non-production preview. Set a new password now.");
      } else {
        setMessage("If the account exists, password reset instructions were issued.");
      }
    } catch {
      setMessage("Failed to request password reset.");
    } finally {
      setLoading(false);
    }
  }

  async function confirmPasswordReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("Updating password...");
    try {
      const response = await fetch(`${apiBase}/auth/password-reset/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ token: resetToken, new_password: newPassword }),
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setMessage(payload.detail ?? "Password reset failed.");
        return;
      }
      setMode("login");
      setPassword("");
      setNewPassword("");
      setMessage("Password updated. Sign in with your new credential.");
    } catch {
      setMessage("Password reset failed.");
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    setLoading(true);
    try {
      const csrf = getCookieValue("omniflow_csrf");
      await fetch(`${apiBase}/auth/session`, {
        method: "DELETE",
        credentials: "include",
        headers: csrf ? { "x-csrf-token": csrf } : undefined
      });
      setMirroredSessionCookie({ authenticated: false, session: null });
      setSession({ authenticated: false, session: null });
      setMessage("Session cleared.");
    } catch {
      setMessage("Failed to clear session.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="surface-card-hero mx-auto max-w-2xl space-y-6 p-6 md:p-8">
        <header className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[rgb(var(--muted-foreground))]">Secure Access</p>
          <h1 className="text-3xl font-semibold tracking-tight text-[rgb(var(--card-foreground))]">Sign in to OmniFlow</h1>
          <p className="max-w-xl text-sm text-[rgb(var(--muted-foreground))]">
            Credential-based authentication is enabled. Create an account, sign in, and reset password from this screen.
          </p>
        </header>
        <div className="flex flex-wrap gap-2">
          <button className="btn-enterprise btn-enterprise-secondary" type="button" onClick={() => setMode("login")}>
            Sign In
          </button>
          <button className="btn-enterprise btn-enterprise-secondary" type="button" onClick={() => setMode("register")}>
            Create Account
          </button>
          <button className="btn-enterprise btn-enterprise-secondary" type="button" onClick={() => setMode("request-reset")}>
            Reset Password
          </button>
        </div>
        <p className="rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--muted))] px-3 py-2 text-sm text-[rgb(var(--card-foreground))]">
          {message}
        </p>
        {mode === "login" && (
          <form className="flex flex-col gap-4 md:max-w-xl" onSubmit={submitLogin}>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Email</span>
              <input
                className="input-enterprise"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="owner@example.com"
                required
              />
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Password</span>
              <input
                className="input-enterprise"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
              />
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Organization (optional)</span>
              {orgOptions.length > 0 ? (
                <select className="input-enterprise" value={orgId} onChange={(event) => setOrgId(event.target.value)}>
                  {orgOptions.map((option) => (
                    <option key={option.org_id} value={option.org_id}>
                      {option.org_name} ({option.role})
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="input-enterprise"
                  value={orgId}
                  onChange={(event) => setOrgId(event.target.value)}
                  placeholder="00000000-0000-0000-0000-000000000000"
                />
              )}
            </label>
            <div className="flex flex-wrap gap-2">
              <button className="btn-enterprise btn-enterprise-primary" disabled={loading} type="submit">
                Sign In
              </button>
              <button
                className="btn-enterprise btn-enterprise-secondary"
                disabled={loading}
                onClick={() => {
                  void loadOrgOptions();
                }}
                type="button"
              >
                Find Organizations
              </button>
              <button
                className="btn-enterprise btn-enterprise-secondary"
                disabled={loading}
                onClick={() => {
                  void checkSession();
                }}
                type="button"
              >
                Check Session
              </button>
              <button
                className="btn-enterprise btn-enterprise-secondary"
                disabled={loading}
                onClick={logout}
                type="button"
              >
                Sign Out
              </button>
            </div>
          </form>
        )}

        {mode === "register" && (
          <form className="flex flex-col gap-4 md:max-w-xl" onSubmit={submitRegister}>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Email</span>
              <input className="input-enterprise" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Password (min 10 chars)</span>
              <input
                className="input-enterprise"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Full Name (optional)</span>
              <input className="input-enterprise" value={fullName} onChange={(event) => setFullName(event.target.value)} />
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Org Name (optional)</span>
              <input className="input-enterprise" value={orgName} onChange={(event) => setOrgName(event.target.value)} />
            </label>
            <button className="btn-enterprise btn-enterprise-primary" disabled={loading} type="submit">
              Create Credential
            </button>
          </form>
        )}

        {mode === "request-reset" && (
          <form className="flex flex-col gap-4 md:max-w-xl" onSubmit={requestPasswordReset}>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Email</span>
              <input className="input-enterprise" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </label>
            <button className="btn-enterprise btn-enterprise-primary" disabled={loading} type="submit">
              Request Password Reset
            </button>
          </form>
        )}

        {mode === "confirm-reset" && (
          <form className="flex flex-col gap-4 md:max-w-xl" onSubmit={confirmPasswordReset}>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Reset Token</span>
              <input className="input-enterprise" value={resetToken} onChange={(event) => setResetToken(event.target.value)} required />
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">New Password</span>
              <input
                className="input-enterprise"
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                required
              />
            </label>
            <button className="btn-enterprise btn-enterprise-primary" disabled={loading} type="submit">
              Update Password
            </button>
          </form>
        )}
      </section>

      {session && (
        <section className="surface-card mx-auto mt-6 max-w-2xl p-5 text-sm">
          <pre className="overflow-x-auto rounded-md bg-[rgb(var(--muted))] p-3">{JSON.stringify(session, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}
