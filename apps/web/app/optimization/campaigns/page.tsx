import { Badge, Card, CardContent, CardHeader, CardTitle, DataTable, EmptyState } from "../../../components/ui/primitives";
import { listPostingOptimizations } from "../../../lib/api";

async function getPostingOptimizations() {
  try {
    return await listPostingOptimizations("meta");
  } catch {
    return [];
  }
}

export default async function OptimizationCampaignsPage() {
  const rows = await getPostingOptimizations();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Post Timing Optimization</h1>
        <p className="page-subtitle">Best channel publish windows computed from deterministic performance cohorts.</p>
      </section>

      {rows.length === 0 ? (
        <EmptyState title="No timing recommendations" description="Recommendations will appear after events include publish and click outcomes." />
      ) : (
        <Card>
          <CardHeader><CardTitle>Timing Windows</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <DataTable>
                <thead><tr><th>Channel</th><th>Best Day</th><th>Best Hour</th><th>Confidence</th><th>Model</th></tr></thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td>{row.channel}</td>
                      <td>{row.best_day_of_week}</td>
                      <td>{row.best_hour}:00</td>
                      <td><Badge tone="info">{Math.round(row.confidence_score * 100)}%</Badge></td>
                      <td>{row.model_version}</td>
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
