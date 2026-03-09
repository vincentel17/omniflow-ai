"use client";

import { useCallback, useEffect, useState } from "react";

import { getApiBaseUrl } from "../../lib/dev-context";
import { readApiError } from "../../lib/http";

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
  return fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body),
    credentials: "include"
  });
}

async function apiGet(path: string): Promise<Response> {
  return fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store",
    credentials: "include"
  });
}

export function ContentQueue({ items }: Props) {
  const [contentItems, setContentItems] = useState(items);
  const [status, setStatus] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const refreshItems = useCallback(async () => {
    const response = await apiGet("/content?limit=50&offset=0");
    if (!response.ok) {
      throw new Error(await readApiError(response, "Refresh failed"));
    }
    setContentItems((await response.json()) as ContentItem[]);
  }, []);

  useEffect(() => {
    if (contentItems.length > 0) {
      return;
    }

    let cancelled = false;
    void refreshItems()
      .then(() => {
        if (!cancelled) {
          setStatus(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : "Refresh failed.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [contentItems.length, refreshItems]);

  async function approve(contentId: string) {
    setPendingAction(`approve-${contentId}`);
    setStatus(null);
    try {
      const response = await apiPost(`/content/${contentId}/approve`, { status: "approved", notes: "Approved in UI" });
      if (!response.ok) {
        setStatus(await readApiError(response, "Approve failed"));
        return;
      }
      await refreshItems();
      setStatus("Content approved.");
    } catch {
      setStatus("Approve failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function schedule(contentId: string) {
    setPendingAction(`schedule-${contentId}`);
    setStatus(null);
    try {
      const response = await apiPost(`/content/${contentId}/schedule`, {
        provider: "linkedin",
        account_ref: "default",
        schedule_at: null
      });
      if (!response.ok) {
        setStatus(await readApiError(response, "Schedule failed"));
        return;
      }
      await refreshItems();
      setStatus("Publish job queued.");
    } catch {
      setStatus("Schedule failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="mt-6 space-y-4">
      {status ? <p className="text-sm text-slate-300" data-testid="content-status-message">{status}</p> : null}
      <button
        className="rounded bg-slate-700 px-3 py-1 text-sm"
        data-testid="content-refresh"
        disabled={pendingAction !== null}
        onClick={() => {
          setPendingAction("refresh");
          void refreshItems()
            .catch((error: unknown) => setStatus(error instanceof Error ? error.message : "Refresh failed."))
            .finally(() => setPendingAction(null));
        }}
        type="button"
      >
        {pendingAction === "refresh" ? "Refreshing..." : "Refresh"}
      </button>
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
              {(() => {
                const normalized = item.status.toLowerCase();
                const approveDisabled = normalized !== "draft" && normalized !== "pending_approval";
                const scheduleDisabled = normalized !== "approved";
                const approving = pendingAction === `approve-${item.id}`;
                const scheduling = pendingAction === `schedule-${item.id}`;
                return (
                  <>
                    <button
                      className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900 disabled:opacity-50"
                      data-testid={contentItems[0]?.id === item.id ? "tour-drafts-approve" : `content-approve-${item.id}`}
                      onClick={() => approve(item.id)}
                      disabled={approveDisabled || pendingAction !== null}
                      type="button"
                    >
                      {approving ? "Approving..." : "Approve"}
                    </button>
                    <button
                      className="rounded bg-slate-700 px-3 py-1 text-sm disabled:opacity-50"
                      data-testid={contentItems[0]?.id === item.id ? "tour-publish-schedule" : `content-schedule-${item.id}`}
                      onClick={() => schedule(item.id)}
                      disabled={scheduleDisabled || pendingAction !== null}
                      type="button"
                    >
                      {scheduling ? "Scheduling..." : "Schedule"}
                    </button>
                  </>
                );
              })()}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
