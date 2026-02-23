import { apiFetch } from "../../../lib/api";

type WorkloadResponse = {
  estimated_minutes_saved_total: number;
  breakdown_by_action_type: Record<string, number>;
  automation_coverage_rate: number;
};

export default async function AnalyticsWorkloadPage() {
  const data = await apiFetch<WorkloadResponse>("/analytics/workload");

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">Workload Reduction Index</h1>
      <p className="mt-2 text-slate-400">Estimated operator time saved from automation actions.</p>
      <section className="mt-6 rounded border border-slate-800 p-4">
        <p className="text-sm text-slate-300">
          Minutes saved: {data.estimated_minutes_saved_total} | Coverage: {data.automation_coverage_rate}%
        </p>
        <pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-3 text-xs">
          {JSON.stringify(data.breakdown_by_action_type, null, 2)}
        </pre>
      </section>
    </main>
  );
}
