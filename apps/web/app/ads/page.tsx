import Link from "next/link";

import { apiFetch } from "../../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/primitives";

type AdsSettings = {
  enable_ads_automation: boolean;
  enable_ads_live: boolean;
  ads_canary_mode: boolean;
  require_approval_for_ads: boolean;
  ads_budget_caps_json: {
    org_daily_cap_usd?: number;
    org_monthly_cap_usd?: number;
    per_campaign_cap_usd?: number;
  };
};

async function getAdsSettings(): Promise<AdsSettings | null> {
  try {
    return await apiFetch<AdsSettings>("/ads/settings");
  } catch {
    return null;
  }
}

export default async function AdsOverviewPage() {
  const settings = await getAdsSettings();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Ads Automation</h1>
        <p className="page-subtitle">Guarded ads operations with caps, approvals, and provider-level controls.</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card><CardHeader><CardTitle>Automation</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{settings?.enable_ads_automation ? "On" : "Off"}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Live Ads</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{settings?.enable_ads_live ? "On" : "Off"}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Canary Mode</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{settings?.ads_canary_mode ? "On" : "Off"}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Approval Gate</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{settings?.require_approval_for_ads ? "Required" : "Optional"}</p></CardContent></Card>
      </section>

      <section className="surface-card p-6 text-sm text-[rgb(var(--muted-foreground))]">
        <p>Daily cap: ${settings?.ads_budget_caps_json?.org_daily_cap_usd ?? 0}</p>
        <p>Monthly cap: ${settings?.ads_budget_caps_json?.org_monthly_cap_usd ?? 0}</p>
        <p>Per campaign cap: ${settings?.ads_budget_caps_json?.per_campaign_cap_usd ?? 0}</p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Link className="surface-card p-4 hover:bg-[rgb(var(--muted))]" href="/ads/campaigns">Campaigns</Link>
        <Link className="surface-card p-4 hover:bg-[rgb(var(--muted))]" href="/ads/creatives">Creatives</Link>
        <Link className="surface-card p-4 hover:bg-[rgb(var(--muted))]" href="/ads/experiments">Experiments</Link>
      </section>
    </main>
  );
}
