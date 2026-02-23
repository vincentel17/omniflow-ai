"use client";

import { useState } from "react";

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

export function PublishJobsTable({ jobs }: Props) {
  const [status, setStatus] = useState<string | null>(null);

  async function cancel(jobId: string) {
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
    setStatus("Job canceled.");
    window.location.reload();
  }

  return (
    <div className="mt-6 space-y-4">
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
      <ul className="space-y-3">
        {jobs.map((job) => (
          <li className="rounded border border-slate-800 p-3" key={job.id}>
            <p className="font-medium">
              {job.provider}/{job.account_ref} | {job.status}
            </p>
            <p className="text-sm text-slate-400">
              attempts={job.attempts} external_id={job.external_id ?? "n/a"}
            </p>
            {job.last_error ? <p className="text-sm text-rose-300">{job.last_error}</p> : null}
            <button className="mt-3 rounded bg-slate-700 px-3 py-1 text-sm" onClick={() => cancel(job.id)} type="button">
              Cancel
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
