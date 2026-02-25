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

export default async function IntegrationsPage() {
  const [accounts, opsSettings] = await Promise.all([getAccounts(), getOpsSettings()]);

  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Integrations</h1>
      <p className="mt-2 text-slate-300">Manage connector mode, provider live flags, and account diagnostics.</p>

      <IntegrationsClient initialSettings={opsSettings} />

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

