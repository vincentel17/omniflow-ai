"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getApiBaseUrl } from "../../../../lib/dev-context";

type DiagnosticsSummary = {
  connector_mode: string;
  ai_mode: string;
  ads_mode: string;
  live_ready: boolean;
  env_checks: Array<{ key: string; required_for_live: boolean; present: boolean }>;
  accounts_linked: number;
  last_sync_at: string | null;
  last_error: string | null;
};

type ConnectorProvider = {
  provider: "google-business-profile" | "meta" | "linkedin";
  mode: string;
  configured: boolean;
};

type StartResponse = {
  authorization_url: string;
};

const PROVIDER_LABELS: Record<ConnectorProvider["provider"], string> = {
  "google-business-profile": "Google Business Profile",
  meta: "Meta",
  linkedin: "LinkedIn"
};

export function IntegrationsDiagnosticsClient() {
  const [summary, setSummary] = useState<DiagnosticsSummary | null>(null);
  const [providers, setProviders] = useState<ConnectorProvider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyProvider, setBusyProvider] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [summaryResponse, providersResponse] = await Promise.all([
        fetch(`${getApiBaseUrl()}/connectors/diagnostics/summary`, { cache: "no-store", credentials: "include" }),
        fetch(`${getApiBaseUrl()}/connectors/providers`, { cache: "no-store", credentials: "include" })
      ]);

      if (!summaryResponse.ok || !providersResponse.ok) {
        setError(`Diagnostics request failed (${summaryResponse.status}/${providersResponse.status}).`);
        return;
      }

      setSummary((await summaryResponse.json()) as DiagnosticsSummary);
      setProviders((await providersResponse.json()) as ConnectorProvider[]);
    } catch {
      setError("Diagnostics unavailable.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function connectProvider(provider: ConnectorProvider["provider"]) {
    setBusyProvider(provider);
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/connectors/${provider}/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include",
        body: JSON.stringify({
          account_ref: "bootstrap",
          display_name: "bootstrap"
        })
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        setError(payload?.detail ?? `Connect failed (${response.status}).`);
        return;
      }

      const payload = (await response.json()) as StartResponse;
      window.location.assign(payload.authorization_url);
    } catch {
      setError("Connect request failed.");
    } finally {
      setBusyProvider(null);
    }
  }

  const providerCards = useMemo(() => {
    return providers
      .filter((item): item is ConnectorProvider => item.provider in PROVIDER_LABELS)
      .map((item) => (
        <article className="rounded-2xl border border-[rgb(var(--border))] p-4" key={item.provider}>
          <p className="text-sm font-semibold">{PROVIDER_LABELS[item.provider]}</p>
          <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">
            Configured: {item.configured ? "yes" : "no"} | Mode: {item.mode}
          </p>
          <button
            className="btn-enterprise btn-enterprise-primary mt-3"
            disabled={busyProvider === item.provider}
            onClick={() => void connectProvider(item.provider)}
            type="button"
          >
            {busyProvider === item.provider ? "Starting..." : "Connect"}
          </button>
        </article>
      ));
  }, [providers, busyProvider]);

  return (
    <section className="surface-card p-6">
      {summary ? (
        <div className="mb-4 rounded-2xl border border-[rgb(var(--border))] p-4 text-sm text-[rgb(var(--muted-foreground))]">
          <p>
            Mode: {summary.connector_mode} | Live ready: {summary.live_ready ? "yes" : "no"} | Accounts linked: {summary.accounts_linked}
          </p>
          <p>
            Last sync: {summary.last_sync_at ?? "n/a"} | Last error: {summary.last_error ?? "n/a"}
          </p>
        </div>
      ) : null}

      {error ? <p className="mb-4 text-sm text-[rgb(var(--danger))]">{error}</p> : null}

      {providerCards.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{providerCards}</div>
      ) : (
        <p className="text-sm text-[rgb(var(--muted-foreground))]">No providers available for this session.</p>
      )}

      <button className="btn-enterprise btn-enterprise-secondary mt-4" onClick={() => void load()} type="button">
        Refresh diagnostics
      </button>
    </section>
  );
}
