"use client";

import { useEffect, useState } from "react";

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

async function apiGet(path: string): Promise<Response> {
  const context = getDevContext();
  return fetch(`${getApiBaseUrl()}${path}`, {
    headers: {
      "X-Omniflow-User-Id": context.userId,
      "X-Omniflow-Org-Id": context.orgId,
      "X-Omniflow-Role": context.role
    },
    cache: "no-store"
  });
}

export function ContentQueue({ items }: Props) {
  const [contentItems, setContentItems] = useState(items);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (contentItems.length > 0) {
      return;
    }

    let cancelled = false;
    void apiGet("/content?limit=50&offset=0")
      .then(async (response) => {
        if (!response.ok || cancelled) {
          return;
        }
        const payload = (await response.json()) as ContentItem[];
        if (!cancelled) {
          setContentItems(payload);
        }
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [contentItems.length]);

  async function approve(contentId: string) {
    const response = await apiPost(`/content/${contentId}/approve`, { status: "approved", notes: "Approved in UI" });
    if (!response.ok) {
      setStatus(`Approve failed (${response.status})`);
      return;
    }
    setContentItems((current) => current.map((item) => (item.id === contentId ? { ...item, status: "approved" } : item)));
    setStatus("Content approved.");
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
    setContentItems((current) => current.map((item) => (item.id === contentId ? { ...item, status: "scheduled" } : item)));
    setStatus("Publish job queued.");
  }

  return (
    <div className="mt-6 space-y-4">
      {status ? <p className="text-sm text-slate-300" data-testid="content-status-message">{status}</p> : null}
      <ul className="space-y-3" data-testid="content-list">
        {contentItems.map((item) => (
          <li className="rounded border border-slate-800 p-3" data-testid={`content-row-${item.id}`} key={item.id}>
            <p className="font-medium">
              {item.channel} | {item.status} | {item.risk_tier}
            </p>
            {item.policy_warnings_json.length > 0 ? (
              <p className="text-sm text-amber-300">Warnings: {item.policy_warnings_json.join(", ")}</p>
            ) : null}
            <div className="mt-3 flex gap-2">
              <button
                className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900"
                data-testid={contentItems[0]?.id === item.id ? "tour-drafts-approve" : `content-approve-${item.id}`}
                onClick={() => approve(item.id)}
                type="button"
              >
                Approve
              </button>
              <button
                className="rounded bg-slate-700 px-3 py-1 text-sm"
                data-testid={contentItems[0]?.id === item.id ? "tour-publish-schedule" : `content-schedule-${item.id}`}
                onClick={() => schedule(item.id)}
                type="button"
              >
                Schedule
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
