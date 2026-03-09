"use client";

import { FormEvent, useState } from "react";

import { getApiBaseUrl } from "../../lib/dev-context";

type Campaign = {
  id: string;
  week_start_date: string;
  status: string;
  vertical_pack_slug: string;
  created_at: string;
};

type Props = { campaigns: Campaign[] };

async function apiPost(path: string, body: unknown): Promise<Response> {
  return fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body),
    credentials: "include"
  });
}

export function CampaignPlanner({ campaigns }: Props) {
  const [items, setItems] = useState(campaigns);
  const [weekStart, setWeekStart] = useState("2026-02-23");
  const [status, setStatus] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<"create" | `generate-${string}` | `approve-${string}` | null>(null);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPendingAction("create");
    setStatus(null);
    try {
      const response = await apiPost("/campaigns/plan", {
        week_start_date: weekStart,
        channels: ["linkedin"],
        objectives: ["Generate attributable pipeline"]
      });
      if (!response.ok) {
        setStatus(`Create failed (${response.status})`);
        return;
      }
      const created = (await response.json()) as Campaign;
      setItems((current) => [created, ...current]);
      setStatus("Campaign plan created.");
    } catch {
      setStatus("Create failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function generateContent(campaignId: string) {
    setPendingAction(`generate-${campaignId}`);
    setStatus(null);
    try {
      const response = await apiPost(`/campaigns/${campaignId}/generate-content`, {});
      if (!response.ok) {
        setStatus(`Generate failed (${response.status})`);
        return;
      }
      setStatus("Content generated.");
    } catch {
      setStatus("Generate failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function approve(campaignId: string) {
    setPendingAction(`approve-${campaignId}`);
    setStatus(null);
    try {
      const response = await apiPost(`/campaigns/${campaignId}/approve`, { status: "approved", notes: "UI approval" });
      if (!response.ok) {
        setStatus(`Approve failed (${response.status})`);
        return;
      }
      setItems((current) =>
        current.map((campaign) => (campaign.id === campaignId ? { ...campaign, status: "approved" } : campaign)),
      );
      setStatus("Campaign approved.");
    } catch {
      setStatus("Approve failed (network error).");
    } finally {
      setPendingAction(null);
    }
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
        <button className="rounded bg-slate-200 px-4 py-2 text-slate-900" data-testid="tour-campaign-create" disabled={pendingAction !== null} type="submit">
          {pendingAction === "create" ? "Generating..." : "Generate Plan"}
        </button>
      </form>
      {status ? <p className="text-sm text-slate-300" data-testid="campaign-status-message">{status}</p> : null}
      <ul className="space-y-3" data-testid="campaign-list">
        {items.map((campaign) => (
          <li className="rounded border border-slate-800 p-3" data-testid={`campaign-row-${campaign.id}`} key={campaign.id}>
            <p className="font-medium">
              {campaign.week_start_date} ({campaign.status})
            </p>
            <p className="text-sm text-slate-400">Pack: {campaign.vertical_pack_slug}</p>
            <div className="mt-3 flex gap-2">
              <button
                className="rounded bg-slate-700 px-3 py-1 text-sm"
                data-testid={items[0]?.id === campaign.id ? "tour-drafts-generate" : `campaign-generate-content-${campaign.id}`}
                onClick={() => generateContent(campaign.id)}
                disabled={pendingAction !== null}
                type="button"
              >
                {pendingAction === `generate-${campaign.id}` ? "Generating..." : "Generate Content"}
              </button>
              <button className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" data-testid={`campaign-approve-${campaign.id}`} onClick={() => approve(campaign.id)} disabled={pendingAction !== null} type="button">
                {pendingAction === `approve-${campaign.id}` ? "Approving..." : "Approve"}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
