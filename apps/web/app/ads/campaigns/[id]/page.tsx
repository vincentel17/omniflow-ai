import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

type AdsCampaignDetail = {
  id: string;
  name: string;
  status: string;
  provider: string;
  daily_budget_usd: number | null;
  last_synced_at: string | null;
  targeting_json: Record<string, unknown>;
  utm_json: Record<string, unknown>;
};

type AdsCampaignDetailPageProps = {
  params: Promise<{ id: string }>;
};

export default async function AdsCampaignDetailPage({ params }: AdsCampaignDetailPageProps) {
  const { id } = await params;
  let campaign: AdsCampaignDetail | null = null;

  try {
    campaign = await apiFetch<AdsCampaignDetail>(`/ads/campaigns/${id}`);
  } catch {
    notFound();
  }

  if (!campaign) {
    notFound();
  }

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6 lg:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[var(--muted-foreground)]">Ads campaign</p>
            <h1 className="text-3xl font-semibold tracking-tight text-[var(--foreground)]">{campaign.name}</h1>
            <p className="text-sm text-[var(--muted-foreground)]">Inspect campaign metadata, targeting, and UTM configuration.</p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link className="button-secondary" href="/ads/campaigns">
              Back to campaigns
            </Link>
            <Link className="button-secondary" href="/ads/creatives">
              View creatives
            </Link>
            <Link className="button-secondary" href="/ads/experiments">
              View experiments
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Status" value={campaign.status} />
        <MetricCard label="Provider" value={campaign.provider} />
        <MetricCard label="Daily budget" value={formatCurrency(campaign.daily_budget_usd)} />
        <MetricCard label="Last synced" value={formatDateTime(campaign.last_synced_at)} />
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <article className={cn("surface-card p-6 lg:p-8", "space-y-3")}>
          <h2 className="text-xl font-semibold text-[var(--foreground)]">Targeting JSON</h2>
          <pre className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--border)] bg-[color-mix(in_oklab,var(--surface)_92%,black_8%)] p-4 text-xs text-[var(--muted-foreground)]">
            {JSON.stringify(campaign.targeting_json, null, 2)}
          </pre>
        </article>
        <article className={cn("surface-card p-6 lg:p-8", "space-y-3")}>
          <h2 className="text-xl font-semibold text-[var(--foreground)]">UTM JSON</h2>
          <pre className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--border)] bg-[color-mix(in_oklab,var(--surface)_92%,black_8%)] p-4 text-xs text-[var(--muted-foreground)]">
            {JSON.stringify(campaign.utm_json, null, 2)}
          </pre>
        </article>
      </section>
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className={cn("surface-panel p-5", "space-y-2")}>
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--muted-foreground)]">{label}</p>
      <p className="text-lg font-semibold text-[var(--foreground)]">{value}</p>
    </article>
  );
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "Never";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatCurrency(value: number | null) {
  if (value === null) {
    return "Not set";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}
