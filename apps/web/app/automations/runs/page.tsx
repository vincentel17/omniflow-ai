import { apiFetch } from "../../../lib/api";
import { DataTable, EmptyState } from "../../../components/ui/primitives";

type WorkflowRun = {
  id: string;
  workflow_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
};

async function getRuns(): Promise<WorkflowRun[]> {
  try {
    return await apiFetch<WorkflowRun[]>("/workflows/runs?limit=50&offset=0");
  } catch {
    return [];
  }
}

export default async function WorkflowRunsPage() {
  const runs = await getRuns();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Workflow Runs</h1>
        <p className="page-subtitle">Execution history for workflow evaluations and action pipelines.</p>
      </section>

      {runs.length === 0 ? (
        <EmptyState title="No workflow runs" description="Runs appear after matching events are evaluated by the workflow worker." />
      ) : (
        <div className="surface-card p-4">
          <DataTable>
            <thead>
              <tr>
                <th>Run</th>
                <th>Workflow</th>
                <th>Status</th>
                <th>Started</th>
                <th>Finished</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="font-mono text-xs">{run.id}</td>
                  <td className="font-mono text-xs">{run.workflow_id}</td>
                  <td>{run.status}</td>
                  <td>{run.started_at ?? "-"}</td>
                  <td>{run.finished_at ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      )}
    </main>
  );
}
