"use client";

import { FormEvent, useMemo, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Checkbox, Select } from "../../../components/ui/primitives";
import { useToast } from "../../../components/ui/toast";
import { getApiBaseUrl } from "../../../lib/dev-context";

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

const providerConnectKeys = [
  { key: "google-business-profile", label: "Google Business Profile" },
  { key: "meta", label: "Meta" },
  { key: "linkedin", label: "LinkedIn" }
] as const;

export function IntegrationsClient({ initialSettings }: Props) {
  const [connectorMode, setConnectorMode] = useState<"mock" | "live">(initialSettings.connector_mode ?? "mock");
  const [providers, setProviders] = useState<Record<string, boolean>>(initialSettings.providers_enabled_json ?? {});
  const [status, setStatus] = useState<string | null>(null);
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);
  const { notify } = useToast();

  const sortedProviders = useMemo(() => providerKeys, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch(`${getApiBaseUrl()}/ops/settings`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "include",
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

  async function startProviderConnect(provider: string) {
    setConnectingProvider(provider);
    setStatus(null);
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
        const message = payload?.detail ?? `Connect failed (${response.status})`;
        setStatus(message);
        notify(message, "error");
        return;
      }
      const payload = (await response.json()) as { authorization_url: string };
      window.location.assign(payload.authorization_url);
    } catch {
      const message = "Connect failed.";
      setStatus(message);
      notify(message, "error");
    } finally {
      setConnectingProvider(null);
    }
  }

  return (
    <Card className="mt-6 ui-fade-in">
      <CardHeader>
        <CardTitle>Connector Controls</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={submit}>
          <label className="block text-sm">
            <span className="mb-1 block text-[rgb(var(--muted-foreground))]">Connector Mode</span>
            <Select className="input-enterprise" onChange={(event) => setConnectorMode(event.target.value as "mock" | "live")} value={connectorMode}>
              <option value="mock">mock</option>
              <option value="live">live</option>
            </Select>
          </label>

          <div className="grid gap-2 sm:grid-cols-2">
            {sortedProviders.map((key) => (
              <label className="ui-hover-lift flex items-center gap-2 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-3 text-sm" key={key}>
                <Checkbox
                  checked={Boolean(providers[key])}
                  onChange={(event) => setProviders((current) => ({ ...current, [key]: event.target.checked }))}
                />
                <span>{key}</span>
              </label>
            ))}
          </div>

          <Button className="btn-enterprise btn-enterprise-primary" type="submit">
            Save Integrations
          </Button>
          <div className="grid gap-2 sm:grid-cols-3">
            {providerConnectKeys.map((provider) => (
              <Button
                className="btn-enterprise btn-enterprise-secondary"
                disabled={Boolean(connectingProvider)}
                key={provider.key}
                onClick={() => {
                  void startProviderConnect(provider.key);
                }}
                type="button"
              >
                {connectingProvider === provider.key ? `Starting ${provider.label}...` : `Connect ${provider.label}`}
              </Button>
            ))}
          </div>
          {status ? (
            <p className="ui-fade-in rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--muted))] px-3 py-2 text-sm text-[rgb(var(--card-foreground))]">{status}</p>
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}
