"use client";

import { FormEvent, useMemo, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Checkbox, Select } from "../../../components/ui/primitives";
import { useToast } from "../../../components/ui/toast";
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
  const { notify } = useToast();

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
      const message = `Save failed (${response.status})`;
      setStatus(message);
      notify(message, "error");
      return;
    }

    setStatus("Integration settings saved.");
    notify("Integrations updated.", "success");
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Connector Controls</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={submit}>
          <label className="block text-sm">
            <span className="mb-1 block text-[rgb(var(--muted-foreground))]">Connector Mode</span>
            <Select onChange={(event) => setConnectorMode(event.target.value as "mock" | "live")} value={connectorMode}>
              <option value="mock">mock</option>
              <option value="live">live</option>
            </Select>
          </label>

          <div className="grid gap-2 sm:grid-cols-2">
            {sortedProviders.map((key) => (
              <label className="flex items-center gap-2 rounded-xl border border-[rgb(var(--border))] p-3 text-sm" key={key}>
                <Checkbox
                  checked={Boolean(providers[key])}
                  onChange={(event) => setProviders((current) => ({ ...current, [key]: event.target.checked }))}
                />
                <span>{key}</span>
              </label>
            ))}
          </div>

          <Button type="submit">Save Integrations</Button>
          {status ? <p className="text-sm text-[rgb(var(--muted-foreground))]">{status}</p> : null}
        </form>
      </CardContent>
    </Card>
  );
}
