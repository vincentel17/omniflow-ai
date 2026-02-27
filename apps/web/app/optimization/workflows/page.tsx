import { Badge, Card, CardContent, CardHeader, CardTitle, DataTable, EmptyState } from "../../../components/ui/primitives";
import { listWorkflowOptimizationSuggestions } from "../../../lib/api";

async function getSuggestions() {
  try {
    return await listWorkflowOptimizationSuggestions();
  } catch {
    return [];
  }
}

export default async function OptimizationWorkflowsPage() {
  const rows = await getSuggestions();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Workflow Optimization Suggestions</h1>
        <p className="page-subtitle">Actionable recommendations from workflow run outcomes, failures, and approval latency.</p>
      </section>

      {rows.length === 0 ? (
        <EmptyState title="No workflow suggestions" description="Suggestions appear after workflow runs and action history accumulate." />
      ) : (
        <Card>
          <CardHeader><CardTitle>Suggestions</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <DataTable>
                <thead><tr><th>Workflow</th><th>Suggestion</th><th>Priority</th></tr></thead>
                <tbody>
                  {rows.map((row, index) => (
                    <tr key={`${row.workflow_key}-${index}`}>
                      <td className="font-mono text-xs">{row.workflow_key.slice(0, 8)}</td>
                      <td>{row.suggestion}</td>
                      <td><Badge tone={row.priority === "high" ? "danger" : row.priority === "medium" ? "warn" : "neutral"}>{row.priority}</Badge></td>
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
