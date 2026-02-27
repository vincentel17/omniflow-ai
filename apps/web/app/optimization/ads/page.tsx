import { Badge, Card, CardContent, CardHeader, CardTitle, DataTable, EmptyState } from "../../../components/ui/primitives";
import { listAdBudgetRecommendations } from "../../../lib/api";

async function getRecommendations() {
  try {
    return await listAdBudgetRecommendations();
  } catch {
    return [];
  }
}

export default async function OptimizationAdsPage() {
  const rows = await getRecommendations();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Ads Budget Recommendations</h1>
        <p className="page-subtitle">Recommendation-only budget optimization with reasoning and projected CPL impact.</p>
      </section>

      {rows.length === 0 ? (
        <EmptyState title="No budget recommendations" description="Create campaigns and sync metrics to generate budget recommendations." />
      ) : (
        <Card>
          <CardHeader><CardTitle>Recommendations</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <DataTable>
                <thead><tr><th>Campaign</th><th>Recommended Daily Budget</th><th>Projected CPL</th><th>Model</th><th>Created</th></tr></thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td className="font-mono text-xs">{row.campaign_id.slice(0, 8)}</td>
                      <td>${row.recommended_daily_budget.toFixed(2)}</td>
                      <td><Badge tone="warn">${row.projected_cpl.toFixed(2)}</Badge></td>
                      <td>{row.model_version}</td>
                      <td>{new Date(row.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            </div>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
