"use client";

import { FormEvent, useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type BrandProfile = {
  brand_voice_json: Record<string, unknown>;
  auto_approve_tiers_max: number;
  require_approval_for_publish: boolean;
};

type Props = { initial: BrandProfile | null };

export function BrandProfileForm({ initial }: Props) {
  const [tone, setTone] = useState(String(initial?.brand_voice_json?.tone ?? "clear, practical"));
  const [autoApprove, setAutoApprove] = useState(initial?.auto_approve_tiers_max ?? 1);
  const [requireApproval, setRequireApproval] = useState(initial?.require_approval_for_publish ?? true);
  const [status, setStatus] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = getDevContext();
    const response = await fetch(`${getApiBaseUrl()}/brand/profile`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Omniflow-User-Id": context.userId,
        "X-Omniflow-Org-Id": context.orgId,
        "X-Omniflow-Role": context.role
      },
      body: JSON.stringify({
        brand_voice_json: { tone },
        brand_assets_json: {},
        locations_json: [],
        auto_approve_tiers_max: autoApprove,
        require_approval_for_publish: requireApproval
      })
    });
    if (!response.ok) {
      setStatus(`Save failed (${response.status})`);
      return;
    }
    setStatus("Saved.");
  }

  return (
    <form className="mt-6 max-w-xl space-y-4 rounded border border-slate-800 p-4" onSubmit={submit}>
      <label className="block text-sm">
        <span className="text-slate-300">Brand Tone</span>
        <input
          className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2"
          onChange={(event) => setTone(event.target.value)}
          type="text"
          value={tone}
        />
      </label>
      <label className="block text-sm">
        <span className="text-slate-300">Auto-approve max tier</span>
        <input
          className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2"
          max={4}
          min={0}
          onChange={(event) => setAutoApprove(Number(event.target.value))}
          type="number"
          value={autoApprove}
        />
      </label>
      <label className="flex items-center gap-2 text-sm text-slate-300">
        <input checked={requireApproval} onChange={(event) => setRequireApproval(event.target.checked)} type="checkbox" />
        Require approval before publish
      </label>
      <button className="rounded bg-slate-200 px-4 py-2 text-slate-900" type="submit">
        Save
      </button>
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
    </form>
  );
}
