import Link from "next/link";

import { apiFetch } from "../../lib/api";

type OverviewResponse = {
  totals: Record<string, number>;
  avg_response_time_minutes: number | null;
  presence_overall_score_latest: number | null;
  staff_reduction_index: {
    estimated_minutes_saved_total: number;
    breakdown_by_action_type: Record<string, number>;
    automation_coverage_rate: number;
  };
  top_channels: Array<{ channel: string; content_items: number; clicks: number; leads: number }>;
};

export default async function AnalyticsOverviewPage() {
  const data = await apiFetch<OverviewResponse>("/analytics/overview");

  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Analytics Overview</h1>
      <p className="mt-2 text-slate-400">Attribution and operational ROI from unified internal events.</p>
      <nav className="mt-4 flex flex-wrap gap-4 text-sm text-slate-300">
        <Link href="/analytics/content">Content</Link>
        <Link href="/analytics/funnel">Funnel</Link>
        <Link href="/analytics/sla">SLA</Link>
        <Link href="/analytics/presence">Presence</Link>
        <Link href="/analytics/workload">Workload</Link>
      </nav>

      <section className="mt-6 grid gap-4 md:grid-cols-3">
        <article className="rounded border border-slate-800 p-4">
          <h2 className="text-sm text-slate-400">Campaigns</h2>
          <p className="mt-2 text-2xl font-semibold">{data.totals.campaigns_created ?? 0}</p>
        </article>
        <article className="rounded border border-slate-800 p-4">
          <h2 className="text-sm text-slate-400">Publish Success</h2>
          <p className="mt-2 text-2xl font-semibold">{data.totals.publish_succeeded ?? 0}</p>
        </article>
        <article className="rounded border border-slate-800 p-4">
          <h2 className="text-sm text-slate-400">Leads Created</h2>
          <p className="mt-2 text-2xl font-semibold">{data.totals.leads_created ?? 0}</p>
        </article>
      </section>

      <section className="mt-6 rounded border border-slate-800 p-4">
        <h2 className="text-lg font-semibold">Operational Metrics</h2>
        <p className="mt-2 text-sm text-slate-300">
          Avg first response: {data.avg_response_time_minutes ?? "n/a"} min | Presence score:{" "}
          {data.presence_overall_score_latest ?? "n/a"} | Minutes saved:{" "}
          {data.staff_reduction_index.estimated_minutes_saved_total}
        </p>
        <p className="mt-1 text-sm text-slate-300">
          Automation coverage: {data.staff_reduction_index.automation_coverage_rate}%
        </p>
      </section>

      <section className="mt-6 rounded border border-slate-800 p-4">
        <h2 className="text-lg font-semibold">Top Channels</h2>
        <ul className="mt-3 space-y-2">
          {data.top_channels.map((row) => (
            <li className="rounded border border-slate-700 p-3" key={row.channel}>
              <p className="font-medium">{row.channel}</p>
              <p className="text-sm text-slate-400">
                content: {row.content_items} | clicks: {row.clicks} | leads: {row.leads}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

