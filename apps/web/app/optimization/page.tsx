import Link from "next/link";

import { Badge, Card, CardContent, CardHeader, CardTitle, EmptyState } from "../../components/ui/primitives";
import {
  getNurtureRecommendations,
  getOptimizationSettings,
  listAdBudgetRecommendations,
  listOptimizationModels,
  listPostingOptimizations,
  listWorkflowOptimizationSuggestions,
} from "../../lib/api";

type OverviewData = {
  settingsEnabledCount: number;
  modelCount: number;
  postingCount: number;
  adRecsCount: number;
  workflowRecsCount: number;
  nurtureDelays: number[];
};

async function getOverviewData(): Promise<OverviewData> {
  try {
    const [settings, models, posting, adRecs, workflowRecs, nurture] = await Promise.all([
      getOptimizationSettings(),
      listOptimizationModels(),
      listPostingOptimizations(),
      listAdBudgetRecommendations(),
      listWorkflowOptimizationSuggestions(),
      getNurtureRecommendations(),
    ]);
    const settingsEnabledCount = [
      settings.enable_predictive_scoring,
      settings.enable_post_timing_optimization,
      settings.enable_nurture_optimization,
      settings.enable_ad_budget_recommendations,
      settings.auto_apply_low_risk_optimizations,
    ].filter(Boolean).length;

    return {
      settingsEnabledCount,
      modelCount: models.length,
      postingCount: posting.length,
      adRecsCount: adRecs.length,
      workflowRecsCount: workflowRecs.length,
      nurtureDelays: nurture.recommended_delays_minutes,
    };
  } catch {
    return {
      settingsEnabledCount: 0,
      modelCount: 0,
      postingCount: 0,
      adRecsCount: 0,
      workflowRecsCount: 0,
      nurtureDelays: [],
    };
  }
}

export default async function OptimizationOverviewPage() {
  const data = await getOverviewData();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card overflow-hidden">
        <div className="bg-gradient-to-r from-[rgb(var(--primary-deep))]/25 via-[rgb(var(--accent-teal))]/20 to-[rgb(var(--accent-gold))]/20 p-6">
          <h1 className="page-title">Optimization Engine</h1>
          <p className="page-subtitle">Explainable recommendations for lead scoring, timing, ads budgets, and workflow efficiency.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge tone="info">Phase 14</Badge>
            <Badge tone={data.modelCount > 0 ? "success" : "warn"}>Models {data.modelCount}</Badge>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Card><CardHeader><CardTitle>Settings On</CardTitle></CardHeader><CardContent><p className="text-3xl font-semibold">{data.settingsEnabledCount}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Timing Windows</CardTitle></CardHeader><CardContent><p className="text-3xl font-semibold">{data.postingCount}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Ads Recommendations</CardTitle></CardHeader><CardContent><p className="text-3xl font-semibold">{data.adRecsCount}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Workflow Suggestions</CardTitle></CardHeader><CardContent><p className="text-3xl font-semibold">{data.workflowRecsCount}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Nurture Delays</CardTitle></CardHeader><CardContent><p className="text-sm text-[rgb(var(--muted-foreground))]">{data.nurtureDelays.length ? `${data.nurtureDelays.join(" / ")} min` : "No data yet"}</p></CardContent></Card>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Link className="surface-card p-4 hover:bg-[rgb(var(--muted))]" href="/optimization/leads">Predictive Lead Scores</Link>
        <Link className="surface-card p-4 hover:bg-[rgb(var(--muted))]" href="/optimization/campaigns">Post Timing</Link>
        <Link className="surface-card p-4 hover:bg-[rgb(var(--muted))]" href="/optimization/ads">Ads Budget Recommendations</Link>
        <Link className="surface-card p-4 hover:bg-[rgb(var(--muted))]" href="/optimization/workflows">Workflow Suggestions</Link>
      </section>

      {data.modelCount === 0 ? (
        <EmptyState title="No model metadata yet" description="Open the models endpoint once to seed deterministic baseline versions." />
      ) : null}
    </main>
  );
}
