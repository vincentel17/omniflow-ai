"use client";

import { FormEvent, useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../lib/dev-context";

type Campaign = {
  id: string;
  week_start_date: string;
  status: string;
  vertical_pack_slug: string;
  created_at: string;
};

type Props = { campaigns: Campaign[] };

async function apiPost(path: string, body: unknown): Promise<Response> {
  const context = getDevContext();
  return fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Omniflow-User-Id": context.userId,
      "X-Omniflow-Org-Id": context.orgId,
      "X-Omniflow-Role": context.role
    },
    body: JSON.stringify(body)
  });
}

export function CampaignPlanner({ campaigns }: Props) {
  const [weekStart, setWeekStart] = useState("2026-02-23");
  const [status, setStatus] = useState<string | null>(null);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await apiPost("/campaigns/plan", {
      week_start_date: weekStart,
      channels: ["linkedin"],
      objectives: ["Generate attributable pipeline"]
    });
    if (!response.ok) {
      setStatus(`Create failed (${response.status})`);
      return;
    }
    setStatus("Campaign plan created. Refreshing...");
    window.location.reload();
  }

  async function generateContent(campaignId: string) {
    const response = await apiPost(`/campaigns/${campaignId}/generate-content`, {});
    if (!response.ok) {
      setStatus(`Generate failed (${response.status})`);
      return;
    }
    setStatus("Content generated.");
  }

  async function approve(campaignId: string) {
    const response = await apiPost(`/campaigns/${campaignId}/approve`, { status: "approved", notes: "UI approval" });
    if (!response.ok) {
      setStatus(`Approve failed (${response.status})`);
      return;
    }
    setStatus("Campaign approved.");
    window.location.reload();
  }

  return (
    <div className="mt-6 space-y-6">
      <form className="flex max-w-lg items-end gap-3 rounded border border-slate-800 p-4" onSubmit={handleCreate}>
        <div className="flex-1">
          <label className="block text-sm text-slate-300">Week Start</label>
          <input
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2"
            onChange={(event) => setWeekStart(event.target.value)}
            type="date"
            value={weekStart}
          />
        </div>
        <button className="rounded bg-slate-200 px-4 py-2 text-slate-900" type="submit">
          Generate Plan
        </button>
      </form>
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
      <ul className="space-y-3">
        {campaigns.map((campaign) => (
          <li className="rounded border border-slate-800 p-3" key={campaign.id}>
            <p className="font-medium">
              {campaign.week_start_date} ({campaign.status})
            </p>
            <p className="text-sm text-slate-400">Pack: {campaign.vertical_pack_slug}</p>
            <div className="mt-3 flex gap-2">
              <button
                className="rounded bg-slate-700 px-3 py-1 text-sm"
                onClick={() => generateContent(campaign.id)}
                type="button"
              >
                Generate Content
              </button>
              <button className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" onClick={() => approve(campaign.id)} type="button">
                Approve
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
