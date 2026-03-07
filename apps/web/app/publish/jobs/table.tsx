"use client";

import { useEffect, useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type PublishJob = {
  id: string;
  provider: string;
  account_ref: string;
  status: string;
  attempts: number;
  external_id: string | null;
  last_error: string | null;
  created_at: string;
};

type Props = { jobs: PublishJob[] };

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

export function PublishJobsTable({ jobs }: Props) {
  const [items, setItems] = useState(jobs);
  const [status, setStatus] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  useEffect(() => {
    if (items.length > 0) {
      return;
    }

    let cancelled = false;
    void apiGet("/publish/jobs?limit=50&offset=0")
      .then(async (response) => {
        if (!response.ok || cancelled) {
          return;
        }
        const payload = (await response.json()) as PublishJob[];
        if (!cancelled) {
          setItems(payload);
        }
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [items.length]);

  async function cancel(jobId: string) {
    setPendingId(jobId);
    setStatus(null);
    try {
      const context = getDevContext();
      const response = await fetch(`${getApiBaseUrl()}/publish/jobs/${jobId}/cancel`, {
        method: "POST",
        headers: {
          "X-Omniflow-User-Id": context.userId,
          "X-Omniflow-Org-Id": context.orgId,
          "X-Omniflow-Role": context.role
        }
      });
      if (!response.ok) {
        setStatus(`Cancel failed (${response.status})`);
        return;
      }
      setItems((current) => current.map((job) => (job.id === jobId ? { ...job, status: "canceled" } : job)));
      setStatus("Job canceled.");
    } catch {
      setStatus("Cancel failed (network error).");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="mt-6 space-y-4">
      {status ? <p className="text-sm text-slate-300" data-testid="publish-status-message">{status}</p> : null}
      <ul className="space-y-3" data-testid="publish-jobs-list">
        {items.map((job) => (
          <li className="rounded border border-slate-800 p-3" data-testid={`publish-job-row-${job.id}`} key={job.id}>
            <p className="font-medium">
              {job.provider}/{job.account_ref} | {job.status}
            </p>
            <p className="text-sm text-slate-400">
              attempts={job.attempts} external_id={job.external_id ?? "n/a"}
            </p>
            {job.last_error ? <p className="text-sm text-rose-300">{job.last_error}</p> : null}
            <button className="mt-3 rounded bg-slate-700 px-3 py-1 text-sm" data-testid={`publish-cancel-${job.id}`} onClick={() => cancel(job.id)} disabled={pendingId === job.id} type="button">
              {pendingId === job.id ? "Canceling..." : "Cancel"}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
