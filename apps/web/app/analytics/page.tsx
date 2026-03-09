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

const fallbackOverview: OverviewResponse = {
  totals: {},
  avg_response_time_minutes: null,
  presence_overall_score_latest: null,
  staff_reduction_index: {
    estimated_minutes_saved_total: 0,
    breakdown_by_action_type: {},
    automation_coverage_rate: 0
  },
  top_channels: []
};

export default async function AnalyticsOverviewPage() {
  const data = await apiFetch<OverviewResponse>("/analytics/overview").catch(() => fallbackOverview);

  return (
    <main className="page-shell space-y-6" data-testid="tour-analytics-open">
      <section className="space-y-3">
        <h1 className="page-title">Analytics Overview</h1>
        <p className="page-subtitle">Attribution and operational ROI from unified internal events.</p>
      </section>

      <nav className="flex flex-wrap gap-2 text-sm">
        <Link className="btn-enterprise btn-enterprise-secondary focus-ring" href="/analytics/content">
          Content
        </Link>
        <Link className="btn-enterprise btn-enterprise-secondary focus-ring" href="/analytics/funnel">
          Funnel
        </Link>
        <Link className="btn-enterprise btn-enterprise-secondary focus-ring" href="/analytics/sla">
          SLA
        </Link>
        <Link className="btn-enterprise btn-enterprise-secondary focus-ring" href="/analytics/presence">
          Presence
        </Link>
        <Link className="btn-enterprise btn-enterprise-secondary focus-ring" href="/analytics/workload">
          Workload
        </Link>
      </nav>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="surface-card ui-hover-lift p-5">
          <h2 className="text-sm text-[rgb(var(--muted-foreground))]">Campaigns</h2>
          <p className="mt-2 text-2xl font-semibold">{data.totals.campaigns_created ?? 0}</p>
        </article>
        <article className="surface-card ui-hover-lift p-5">
          <h2 className="text-sm text-[rgb(var(--muted-foreground))]">Publish Success</h2>
          <p className="mt-2 text-2xl font-semibold">{data.totals.publish_succeeded ?? 0}</p>
        </article>
        <article className="surface-card ui-hover-lift p-5">
          <h2 className="text-sm text-[rgb(var(--muted-foreground))]">Leads Created</h2>
          <p className="mt-2 text-2xl font-semibold">{data.totals.leads_created ?? 0}</p>
        </article>
      </section>

      <section className="surface-card ui-fade-in p-5">
        <h2 className="text-base font-semibold">Operational Metrics</h2>
        <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">
          Avg first response: {data.avg_response_time_minutes ?? "n/a"} min | Presence score: {data.presence_overall_score_latest ?? "n/a"} | Minutes saved:{" "}
          {data.staff_reduction_index.estimated_minutes_saved_total}
        </p>
        <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Automation coverage: {data.staff_reduction_index.automation_coverage_rate}%</p>
      </section>

      <section className="surface-card ui-fade-in p-5">
        <h2 className="text-base font-semibold">Top Channels</h2>
        <ul className="mt-3 space-y-2">
          {data.top_channels.length === 0 ? (
            <li className="ui-pulse-soft rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--muted))] px-3 py-4 text-sm text-[rgb(var(--muted-foreground))]">
              No channel data available yet.
            </li>
          ) : (
            data.top_channels.map((row) => (
              <li className="ui-hover-lift rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-3" key={row.channel}>
                <p className="font-medium">{row.channel}</p>
                <p className="text-sm text-[rgb(var(--muted-foreground))]">
                  content: {row.content_items} | clicks: {row.clicks} | leads: {row.leads}
                </p>
              </li>
            ))
          )}
        </ul>
      </section>
    </main>
  );
}
