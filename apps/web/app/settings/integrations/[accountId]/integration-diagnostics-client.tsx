"use client";

import { useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../../lib/dev-context";

type Props = {
  accountId: string;
  provider: string;
  accountRef: string;
};

export function IntegrationDiagnosticsClient({ accountId, provider, accountRef }: Props) {
  const [status, setStatus] = useState<string | null>(null);

  async function runHealthcheck() {
    const context = getDevContext();
    const response = await fetch(`${getApiBaseUrl()}/connectors/accounts/${accountId}/healthcheck`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Omniflow-User-Id": context.userId,
        "X-Omniflow-Org-Id": context.orgId,
        "X-Omniflow-Role": context.role
      }
    });
    setStatus(response.ok ? "Healthcheck complete." : `Healthcheck failed (${response.status})`);
  }

  async function resetBreaker() {
    const context = getDevContext();
    const response = await fetch(`${getApiBaseUrl()}/connectors/accounts/${accountId}/breaker/reset`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Omniflow-User-Id": context.userId,
        "X-Omniflow-Org-Id": context.orgId,
        "X-Omniflow-Role": context.role
      }
    });
    setStatus(response.ok ? "Breaker reset." : `Breaker reset failed (${response.status})`);
  }

  async function disconnect() {
    const context = getDevContext();
    const response = await fetch(`${getApiBaseUrl()}/connectors/accounts/${accountId}/revoke`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Omniflow-User-Id": context.userId,
        "X-Omniflow-Org-Id": context.orgId,
        "X-Omniflow-Role": context.role
      }
    });
    setStatus(response.ok ? "Account disconnected." : `Disconnect failed (${response.status})`);
  }

  return (
    <section className="mt-6 space-y-3">
      <h2 className="text-xl font-semibold">Actions</h2>
      <div className="flex flex-wrap gap-3">
        <button className="rounded bg-slate-200 px-3 py-2 text-sm text-slate-900" onClick={runHealthcheck} type="button">
          Run healthcheck
        </button>
        <button className="rounded bg-slate-200 px-3 py-2 text-sm text-slate-900" onClick={resetBreaker} type="button">
          Reset breaker
        </button>
        <button className="rounded bg-red-300 px-3 py-2 text-sm text-slate-900" onClick={disconnect} type="button">
          Disconnect
        </button>
      </div>
      <p className="text-sm text-slate-400">Reauth: use start OAuth for provider `{provider}` account `{accountRef}`.</p>
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
    </section>
  );
}
