import { apiFetch } from "../../../lib/api";

type PresenceResponse = {
  group_by: string;
  audit_runs_count: number;
  score_trend: Array<{
    bucket: string;
    overall_score: number;
    category_scores: Record<string, number>;
  }>;
  open_findings_count: number;
};

export default async function AnalyticsPresencePage() {
  const data = await apiFetch<PresenceResponse>("/analytics/presence?group_by=week");

  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Presence Trends</h1>
      <p className="mt-2 text-slate-400">Audit score trajectory and open findings.</p>
      <section className="mt-6 rounded border border-slate-800 p-4">
        <p className="text-sm text-slate-300">
          Runs: {data.audit_runs_count} | Open findings: {data.open_findings_count}
        </p>
        <pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-3 text-xs">{JSON.stringify(data.score_trend, null, 2)}</pre>
      </section>
    </main>
  );
}

