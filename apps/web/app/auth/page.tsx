"use client";

import { FormEvent, useMemo, useState } from "react";
import { getApiBaseUrl } from "@/lib/dev-context";

type SessionPayload = {
  authenticated: boolean;
  session?: {
    user_id: string;
    org_id: string;
    role: string;
  } | null;
};

export default function AuthPage(): JSX.Element {
  const apiBase = useMemo(() => getApiBaseUrl(), []);
  const [email, setEmail] = useState("");
  const [orgId, setOrgId] = useState("");
  const [message, setMessage] = useState("Use a seeded user email to create an API session cookie.");
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [loading, setLoading] = useState(false);

  async function checkSession() {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/auth/session`, { credentials: "include", cache: "no-store" });
      const payload = (await response.json()) as SessionPayload;
      setSession(payload);
      setMessage(payload.authenticated ? "Session is active." : "No active session.");
    } catch {
      setMessage("Failed to check session.");
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
        body: JSON.stringify({ email, org_id: orgId || undefined }),
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setMessage(payload.detail ?? "Login failed.");
        return;
      }
      await checkSession();
      setMessage("Session created. You can now use session auth mode.");
    } catch {
      setMessage("Login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    setLoading(true);
    try {
      await fetch(`${apiBase}/auth/session`, { method: "DELETE", credentials: "include" });
      setSession({ authenticated: false, session: null });
      setMessage("Session cleared.");
    } catch {
      setMessage("Failed to clear session.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card space-y-3 p-5">
        <h1 className="text-2xl font-semibold">Auth Session</h1>
        <p className="text-sm text-slate-300">{message}</p>
        <form className="flex flex-col gap-3 md:max-w-lg" onSubmit={submitLogin}>
          <label className="space-y-1 text-sm">
            <span>Email</span>
            <input
              className="w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="owner@example.com"
              required
            />
          </label>
          <label className="space-y-1 text-sm">
            <span>Org ID (optional)</span>
            <input
              className="w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2"
              value={orgId}
              onChange={(event) => setOrgId(event.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
            />
          </label>
          <div className="flex gap-2">
            <button className="rounded-md bg-indigo-500 px-4 py-2 text-sm font-medium" disabled={loading} type="submit">
              Sign In
            </button>
            <button
              className="rounded-md border border-slate-600 px-4 py-2 text-sm font-medium"
              disabled={loading}
              onClick={checkSession}
              type="button"
            >
              Check Session
            </button>
            <button
              className="rounded-md border border-slate-600 px-4 py-2 text-sm font-medium"
              disabled={loading}
              onClick={logout}
              type="button"
            >
              Sign Out
            </button>
          </div>
        </form>
      </section>

      {session && (
        <section className="surface-card p-5 text-sm">
          <pre>{JSON.stringify(session, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}
