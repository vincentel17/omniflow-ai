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
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Integrations</h1>
      <p className="mt-2 text-slate-300">Manage connector mode, provider live flags, and account diagnostics.</p>

      <IntegrationsClient initialSettings={opsSettings} />

      <section className="mt-8 rounded border border-slate-800 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Connector Diagnostics</h2>
          <Link className="rounded bg-slate-800 px-3 py-2 text-sm text-slate-100" href="/settings/integrations/diagnostics">
            Open full diagnostics
          </Link>
        </div>
        {!diagnostics ? (
          <p className="mt-2 text-slate-400">Diagnostics unavailable.</p>
        ) : (
          <>
            <p className="mt-2 text-sm text-slate-300">
              Mode: {diagnostics.connector_mode} | AI: {diagnostics.ai_mode} | ADS: {diagnostics.ads_mode}
            </p>
            <p className="text-sm text-slate-300">
              Accounts linked: {diagnostics.accounts_linked} | Live ready: {diagnostics.live_ready ? "yes" : "no"}
            </p>
            <p className="text-sm text-slate-400">
              Last sync: {diagnostics.last_sync_at ?? "n/a"} | Last error: {diagnostics.last_error ?? "n/a"}
            </p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {diagnostics.env_checks.map((item) => (
                <li className="rounded border border-slate-700 px-3 py-2 text-sm" key={item.key}>
                  <span className="font-medium">{item.key}</span>: {item.present ? "present" : "missing"}
                  {item.required_for_live ? " (required)" : " (optional)"}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-semibold">Connected Accounts</h2>
        {accounts.length === 0 ? (
          <p className="mt-3 text-slate-400">No connector accounts linked yet.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {accounts.map((account) => (
              <li className="rounded border border-slate-800 p-3" key={account.id}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-slate-100">{account.display_name}</p>
                    <p className="text-sm text-slate-400">
                      {account.provider} | {account.account_ref} | {account.status}
                    </p>
                  </div>
                  <Link className="rounded bg-slate-200 px-3 py-2 text-sm text-slate-900" href={`/settings/integrations/${account.id}`}>
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

