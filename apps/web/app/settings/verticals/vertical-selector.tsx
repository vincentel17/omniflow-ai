"use client";

import { FormEvent, useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type Props = {
  packs: string[];
};

export function VerticalSelector({ packs }: Props) {
  const [selected, setSelected] = useState(packs[0] ?? "generic");
  const [status, setStatus] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = getDevContext();
    const response = await fetch(`${getApiBaseUrl()}/verticals/select`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Omniflow-User-Id": context.userId,
        "X-Omniflow-Org-Id": context.orgId,
        "X-Omniflow-Role": context.role
      },
      body: JSON.stringify({ pack_slug: selected })
    });
    if (!response.ok) {
      setStatus(`Failed (${response.status})`);
      return;
    }
    setStatus(`Selected: ${selected}`);
  }

  return (
    <form className="mt-6 flex max-w-md gap-3" onSubmit={handleSubmit}>
      <select
        className="flex-1 rounded border border-slate-700 bg-slate-900 p-2 text-slate-100"
        onChange={(event) => setSelected(event.target.value)}
        value={selected}
      >
        {packs.map((pack) => (
          <option key={pack} value={pack}>
            {pack}
          </option>
        ))}
      </select>
      <button className="rounded bg-slate-200 px-4 py-2 text-slate-900" type="submit">
        Save
      </button>
      {status ? <span className="self-center text-sm text-slate-300">{status}</span> : null}
    </form>
  );
}
