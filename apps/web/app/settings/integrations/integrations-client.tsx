"use client";

import { FormEvent, useMemo, useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type Props = {
  initialSettings: {
    connector_mode: "mock" | "live";
    providers_enabled_json: Record<string, boolean>;
  };
};

const providerKeys = [
  "gbp_publish_enabled",
  "meta_publish_enabled",
  "linkedin_publish_enabled",
  "gbp_inbox_enabled",
  "meta_inbox_enabled",
  "linkedin_inbox_enabled"
] as const;

export function IntegrationsClient({ initialSettings }: Props) {
  const [connectorMode, setConnectorMode] = useState<"mock" | "live">(initialSettings.connector_mode ?? "mock");
  const [providers, setProviders] = useState<Record<string, boolean>>(initialSettings.providers_enabled_json ?? {});
  const [status, setStatus] = useState<string | null>(null);

  const sortedProviders = useMemo(() => providerKeys, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = getDevContext();
    const response = await fetch(`${getApiBaseUrl()}/ops/settings`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-Omniflow-User-Id": context.userId,
        "X-Omniflow-Org-Id": context.orgId,
        "X-Omniflow-Role": context.role
      },
      body: JSON.stringify({
        connector_mode: connectorMode,
        providers_enabled_json: providers
      })
    });

    if (!response.ok) {
      setStatus(`Save failed (${response.status})`);
      return;
    }

    setStatus("Integration settings saved.");
  }

  return (
    <form className="mt-6 space-y-4 rounded border border-slate-800 p-4" onSubmit={submit}>
      <label className="block text-sm">
        <span className="text-slate-300">Connector Mode</span>
        <select
          className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2"
          onChange={(event) => setConnectorMode(event.target.value as "mock" | "live")}
          value={connectorMode}
        >
          <option value="mock">mock</option>
          <option value="live">live</option>
        </select>
      </label>

      <div className="grid gap-2 sm:grid-cols-2">
        {sortedProviders.map((key) => (
          <label className="flex items-center gap-2 rounded border border-slate-800 p-2 text-sm" key={key}>
            <input
              checked={Boolean(providers[key])}
              onChange={(event) => setProviders((current) => ({ ...current, [key]: event.target.checked }))}
              type="checkbox"
            />
            <span className="text-slate-300">{key}</span>
          </label>
        ))}
      </div>

      <button className="rounded bg-slate-200 px-4 py-2 text-slate-900" type="submit">
        Save Integrations
      </button>
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
    </form>
  );
}
