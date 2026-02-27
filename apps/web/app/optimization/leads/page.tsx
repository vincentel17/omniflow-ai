import { Badge, Card, CardContent, CardHeader, CardTitle, DataTable, EmptyState } from "../../../components/ui/primitives";
import { listOptimizationModels } from "../../../lib/api";

async function getLeadModels() {
  try {
    const rows = await listOptimizationModels();
    return rows.filter((row) => row.name.startsWith("lead_score_model"));
  } catch {
    return [];
  }
}

export default async function OptimizationLeadsPage() {
  const models = await getLeadModels();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Predictive Lead Scoring</h1>
        <p className="page-subtitle">Model versions, activation status, and explainability-first scoring metadata.</p>
      </section>

      {models.length === 0 ? (
        <EmptyState title="No lead scoring models" description="Model metadata appears after optimization model listing is initialized." />
      ) : (
        <Card>
          <CardHeader><CardTitle>Lead Score Models</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <DataTable>
                <thead><tr><th>Name</th><th>Version</th><th>Status</th><th>Trained</th></tr></thead>
                <tbody>
                  {models.map((row) => (
                    <tr key={row.id}>
                      <td>{row.name}</td>
                      <td>{row.version}</td>
                      <td><Badge tone={row.status === "active" ? "success" : row.status === "degraded" ? "warn" : "neutral"}>{row.status}</Badge></td>
                      <td>{new Date(row.trained_at).toLocaleString()}</td>
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
