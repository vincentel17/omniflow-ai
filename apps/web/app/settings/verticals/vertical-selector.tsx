"use client";

import { FormEvent, useMemo, useState } from "react";

import type { VerticalPackManifest } from "../../../lib/api";
import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type Props = {
  packs: VerticalPackManifest[];
  currentPack: string | null;
};

function featureList(features: Record<string, boolean>): string {
  return Object.entries(features)
    .filter(([, enabled]) => enabled)
    .map(([key]) => key.replace(/_/g, " "))
    .join(", ");
}

export function VerticalSelector({ packs, currentPack }: Props) {
  const defaultPack = currentPack ?? packs[0]?.slug ?? "generic";
  const [selected, setSelected] = useState(defaultPack);
  const [status, setStatus] = useState<string | null>(null);

  const selectedPack = useMemo(() => packs.find((pack) => pack.slug === selected) ?? null, [packs, selected]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("Saving...");
    const context = getDevContext();
    const response = await fetch(`${getApiBaseUrl()}/verticals/select`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Omniflow-User-Id": context.userId,
        "X-Omniflow-Org-Id": context.orgId,
        "X-Omniflow-Role": context.role,
      },
      body: JSON.stringify({ pack_slug: selected }),
    });

    if (!response.ok) {
      const detail = await response.text();
      setStatus(`Failed (${response.status}): ${detail.slice(0, 120)}`);
      return;
    }
    setStatus(`Selected: ${selected}`);
  }

  return (
    <section className="surface-card p-4">
      <form className="flex flex-col gap-4 md:flex-row md:items-center" onSubmit={handleSubmit}>
        <select
          className="min-w-[260px] rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-2 text-[rgb(var(--foreground))]"
          onChange={(event) => setSelected(event.target.value)}
          value={selected}
        >
          {packs.map((pack) => (
            <option key={pack.slug} value={pack.slug}>
              {pack.name} ({pack.slug})
            </option>
          ))}
        </select>
        <button className="rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-medium text-white" type="submit">
          Activate Pack
        </button>
        {status ? <span className="text-sm text-[rgb(var(--muted-foreground))]">{status}</span> : null}
      </form>

      {selectedPack ? (
        <div className="mt-4 rounded-xl border border-[rgb(var(--border))] p-3 text-sm text-[rgb(var(--muted-foreground))]">
          <p className="font-medium text-[rgb(var(--foreground))]">Manifest details</p>
          <p className="mt-1">Version: {selectedPack.version}</p>
          <p>Core compatibility: {selectedPack.compatible_core_version}</p>
          <p>Features: {featureList(selectedPack.features) || "none"}</p>
          <p className="break-all">Checksum: {selectedPack.checksum}</p>
        </div>
      ) : null}
    </section>
  );
}
