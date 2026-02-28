import { Badge, Card, CardContent, CardHeader, CardTitle, DataTable, EmptyState } from "../../../components/ui/primitives";
import { listPredictiveLeadScores } from "../../../lib/api";

async function getLeadScores() {
  try {
    return await listPredictiveLeadScores();
  } catch {
    return [];
  }
}

export default async function OptimizationLeadsPage() {
  const rows = await getLeadScores();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Predictive Lead Scoring</h1>
        <p className="page-subtitle">Stored predictive scores with confidence and feature-attribution explanation.</p>
      </section>

      {rows.length === 0 ? (
        <EmptyState title="No predictive lead scores" description="Run lead scoring from API or workflow hooks to populate this view." />
      ) : (
        <Card>
          <CardHeader><CardTitle>Lead Predictions</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <DataTable>
                <thead><tr><th>Lead</th><th>Model</th><th>Probability</th><th>Explanation</th><th>Scored</th></tr></thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td className="font-mono text-xs">{row.lead_id.slice(0, 8)}</td>
                      <td>{row.model_version}</td>
                      <td><Badge tone="info">{Math.round(row.score_probability * 100)}%</Badge></td>
                      <td>{row.explanation}</td>
                      <td>{new Date(row.scored_at).toLocaleString()}</td>
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
