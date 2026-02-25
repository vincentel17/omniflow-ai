import { apiFetch } from "../../../lib/api";

type SLAResponse = {
  avg_first_response_time_minutes: number | null;
  within_sla_percent: number;
  escalations_triggered: number;
  overdue_threads_count: number;
};

export default async function AnalyticsSLAPage() {
  const data = await apiFetch<SLAResponse>("/analytics/sla");

  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">SLA Analytics</h1>
      <p className="mt-2 text-slate-400">Response-time performance and escalations.</p>
      <section className="mt-6 rounded border border-slate-800 p-4">
        <pre className="overflow-x-auto rounded bg-slate-900 p-3 text-xs">{JSON.stringify(data, null, 2)}</pre>
      </section>
    </main>
  );
}

