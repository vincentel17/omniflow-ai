import Link from "next/link";

import { apiFetch } from "../../../lib/api";
import { IntegrationsClient } from "./integrations-client";

type ConnectorAccount = {
  id: string;
  provider: string;
  account_ref: string;
  display_name: string;
  status: string;
  created_at: string;
};

type OpsSettings = {
  connector_mode: "mock" | "live";
  providers_enabled_json: Record<string, boolean>;
};

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

async function getAccounts(): Promise<ConnectorAccount[]> {
  try {
    return await apiFetch<ConnectorAccount[]>("/connectors/accounts");
  } catch {
    return [];
  }
}

async function getOpsSettings(): Promise<OpsSettings> {
  try {
    return await apiFetch<OpsSettings>("/ops/settings");
  } catch {
    return { connector_mode: "mock", providers_enabled_json: {} };
  }
}

async function getDiagnosticsSummary(): Promise<DiagnosticsSummary | null> {
  try {
    return await apiFetch<DiagnosticsSummary>("/connectors/diagnostics/summary");
  } catch {
    return null;
  }
}

export default async function IntegrationsPage() {
  const [accounts, opsSettings, diagnostics] = await Promise.all([getAccounts(), getOpsSettings(), getDiagnosticsSummary()]);

  return (
    <main className="page-shell space-y-6">
      <section className="space-y-3">
        <h1 className="page-title">Integrations</h1>
        <p className="page-subtitle">Manage connector mode, provider live flags, and account diagnostics.</p>
      </section>

      <IntegrationsClient initialSettings={opsSettings} />

      <section className="surface-card ui-fade-in p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold">Connector Diagnostics</h2>
          <Link className="btn-enterprise btn-enterprise-secondary focus-ring" href="/settings/integrations/diagnostics">
            Open full diagnostics
          </Link>
        </div>
        {!diagnostics ? (
          <p className="ui-pulse-soft mt-2 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--muted))] px-3 py-2 text-sm text-[rgb(var(--muted-foreground))]">
            Diagnostics unavailable.
          </p>
        ) : (
          <>
            <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">
              Mode: {diagnostics.connector_mode} | AI: {diagnostics.ai_mode} | ADS: {diagnostics.ads_mode}
            </p>
            <p className="text-sm text-[rgb(var(--muted-foreground))]">
              Accounts linked: {diagnostics.accounts_linked} | Live ready: {diagnostics.live_ready ? "yes" : "no"}
            </p>
            <p className="text-sm text-[rgb(var(--muted-foreground))]">
              Last sync: {diagnostics.last_sync_at ?? "n/a"} | Last error: {diagnostics.last_error ?? "n/a"}
            </p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {diagnostics.env_checks.map((item) => (
                <li className="ui-hover-lift rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm" key={item.key}>
                  <span className="font-medium">{item.key}</span>: {item.present ? "present" : "missing"}
                  {item.required_for_live ? " (required)" : " (optional)"}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="surface-card ui-fade-in p-5">
        <h2 className="text-base font-semibold">Connected Accounts</h2>
        {accounts.length === 0 ? (
          <p className="ui-pulse-soft mt-3 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--muted))] px-3 py-2 text-sm text-[rgb(var(--muted-foreground))]">
            No connector accounts linked yet.
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {accounts.map((account) => (
              <li className="ui-hover-lift rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-3" key={account.id}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-[rgb(var(--card-foreground))]">{account.display_name}</p>
                    <p className="text-sm text-[rgb(var(--muted-foreground))]">
                      {account.provider} | {account.account_ref} | {account.status}
                    </p>
                  </div>
                  <Link className="btn-enterprise btn-enterprise-secondary focus-ring" href={`/settings/integrations/${account.id}`}>
                    Diagnostics
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

