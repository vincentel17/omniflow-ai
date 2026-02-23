"use client";

import { useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../lib/dev-context";

type AuditRun = {
  id: string;
  status: string;
  summary_scores_json: { overall_score?: number; category_scores?: Record<string, number> };
  created_at: string;
};

type Finding = {
  id: string;
  source: string;
  category: string;
  severity: string;
  title: string;
  status: string;
};

type PresenceTask = {
  id: string;
  type: string;
  status: string;
  payload_json: Record<string, unknown>;
};

type Props = {
  initialLatest: AuditRun | null;
  initialFindings: Finding[];
  initialTasks: PresenceTask[];
};

function headers(): Record<string, string> {
  const context = getDevContext();
  return {
    "Content-Type": "application/json",
    "X-Omniflow-User-Id": context.userId,
    "X-Omniflow-Org-Id": context.orgId,
    "X-Omniflow-Role": context.role
  };
}

export function PresenceConsole({ initialLatest, initialFindings, initialTasks }: Props) {
  const [latest, setLatest] = useState<AuditRun | null>(initialLatest);
  const [findings, setFindings] = useState<Finding[]>(initialFindings);
  const [tasks, setTasks] = useState<PresenceTask[]>(initialTasks);
  const [status, setStatus] = useState<string | null>(null);

  async function refresh() {
    const [latestRes, findingsRes, tasksRes] = await Promise.all([
      fetch(`${getApiBaseUrl()}/presence`, { headers: headers(), cache: "no-store" }),
      fetch(`${getApiBaseUrl()}/presence/findings?limit=20&offset=0`, { headers: headers(), cache: "no-store" }),
      fetch(`${getApiBaseUrl()}/presence/tasks?limit=20&offset=0`, { headers: headers(), cache: "no-store" })
    ]);
    if (!latestRes.ok || !findingsRes.ok || !tasksRes.ok) {
      setStatus("Refresh failed.");
      return;
    }
    setLatest((await latestRes.json()) as AuditRun | null);
    setFindings((await findingsRes.json()) as Finding[]);
    setTasks((await tasksRes.json()) as PresenceTask[]);
  }

  async function runAudit() {
    const response = await fetch(`${getApiBaseUrl()}/presence/audits/run`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        providers_to_audit: ["gbp", "meta", "linkedin", "website"],
        website_url: "https://example.com",
        run_mode: "manual"
      })
    });
    if (!response.ok) {
      setStatus(`Audit failed (${response.status})`);
      return;
    }
    setStatus("Presence audit completed.");
    await refresh();
  }

  async function markDone(findingId: string) {
    const response = await fetch(`${getApiBaseUrl()}/presence/findings/${findingId}`, {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify({ status: "done" })
    });
    if (!response.ok) {
      setStatus(`Update failed (${response.status})`);
      return;
    }
    setStatus("Finding updated.");
    await refresh();
  }

  return (
    <div className="mt-6 grid gap-6">
      <section className="rounded border border-slate-800 p-4">
        <button className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" onClick={runAudit} type="button">
          Run Presence Audit
        </button>
        {latest ? (
          <p className="mt-3 text-sm text-slate-300">
            Latest score: <span className="font-semibold">{latest.summary_scores_json.overall_score ?? "n/a"}</span>
          </p>
        ) : (
          <p className="mt-3 text-sm text-slate-400">No audit runs yet.</p>
        )}
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Findings</h2>
        <ul className="mt-3 space-y-2">
          {findings.map((finding) => (
            <li className="rounded border border-slate-700 p-3" key={finding.id}>
              <p className="font-medium">
                [{finding.severity}] {finding.title}
              </p>
              <p className="text-sm text-slate-400">
                {finding.source} / {finding.category} / {finding.status}
              </p>
              {finding.status !== "done" ? (
                <button
                  className="mt-2 rounded bg-slate-700 px-3 py-1 text-sm"
                  onClick={() => markDone(finding.id)}
                  type="button"
                >
                  Mark Done
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Suggested Tasks</h2>
        <ul className="mt-3 space-y-2">
          {tasks.map((task) => (
            <li className="rounded border border-slate-700 p-3" key={task.id}>
              <p className="font-medium">{task.type}</p>
              <p className="text-sm text-slate-400">{task.status}</p>
            </li>
          ))}
        </ul>
      </section>
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
    </div>
  );
}
