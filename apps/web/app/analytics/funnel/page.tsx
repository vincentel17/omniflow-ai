import { apiFetch } from "../../../lib/api";

type FunnelResponse = {
  stages: Record<string, number>;
  conversion_rates: Record<string, number>;
};

export default async function AnalyticsFunnelPage() {
  const data = await apiFetch<FunnelResponse>("/analytics/funnel");

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">Funnel Analytics</h1>
      <p className="mt-2 text-slate-400">Inbox-to-outcome conversion path.</p>
      <section className="mt-6 rounded border border-slate-800 p-4">
        <h2 className="text-lg font-semibold">Stages</h2>
        <pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-3 text-xs">{JSON.stringify(data.stages, null, 2)}</pre>
      </section>
      <section className="mt-6 rounded border border-slate-800 p-4">
        <h2 className="text-lg font-semibold">Conversion Rates (%)</h2>
        <pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-3 text-xs">
          {JSON.stringify(data.conversion_rates, null, 2)}
        </pre>
      </section>
    </main>
  );
}
