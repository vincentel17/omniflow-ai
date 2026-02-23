"use client";

import { useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../lib/dev-context";

type ContentItem = {
  id: string;
  campaign_plan_id: string;
  channel: string;
  status: string;
  risk_tier: string;
  policy_warnings_json: string[];
  created_at: string;
};

type Props = { items: ContentItem[] };

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

export function ContentQueue({ items }: Props) {
  const [status, setStatus] = useState<string | null>(null);

  async function approve(contentId: string) {
    const response = await apiPost(`/content/${contentId}/approve`, { status: "approved", notes: "Approved in UI" });
    if (!response.ok) {
      setStatus(`Approve failed (${response.status})`);
      return;
    }
    setStatus("Content approved.");
    window.location.reload();
  }

  async function schedule(contentId: string) {
    const response = await apiPost(`/content/${contentId}/schedule`, {
      provider: "linkedin",
      account_ref: "default",
      schedule_at: null
    });
    if (!response.ok) {
      setStatus(`Schedule failed (${response.status})`);
      return;
    }
    setStatus("Publish job queued.");
    window.location.reload();
  }

  return (
    <div className="mt-6 space-y-4">
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
      <ul className="space-y-3">
        {items.map((item) => (
          <li className="rounded border border-slate-800 p-3" key={item.id}>
            <p className="font-medium">
              {item.channel} | {item.status} | {item.risk_tier}
            </p>
            {item.policy_warnings_json.length > 0 ? (
              <p className="text-sm text-amber-300">Warnings: {item.policy_warnings_json.join(", ")}</p>
            ) : null}
            <div className="mt-3 flex gap-2">
              <button className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" onClick={() => approve(item.id)} type="button">
                Approve
              </button>
              <button className="rounded bg-slate-700 px-3 py-1 text-sm" onClick={() => schedule(item.id)} type="button">
                Schedule
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
