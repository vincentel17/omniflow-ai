import { apiFetch } from "../../../lib/api";
import { Card, CardContent, CardHeader, CardTitle, EmptyState } from "../../../components/ui/primitives";

type Workflow = {
  id: string;
  key: string;
  name: string;
  enabled: boolean;
  trigger_type: string;
};

async function getWorkflows(): Promise<Workflow[]> {
  try {
    return await apiFetch<Workflow[]>("/workflows?limit=50&offset=0");
  } catch {
    return [];
  }
}

export default async function WorkflowsPage() {
  const workflows = await getWorkflows();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Workflows</h1>
        <p className="page-subtitle">Phase 10 automation definitions, trigger types, and enablement status.</p>
      </section>

      {workflows.length === 0 ? (
        <EmptyState title="No workflows yet" description="Create a workflow pack assignment or add definitions from the workflows API." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {workflows.map((workflow) => (
            <Card key={workflow.id}>
              <CardHeader>
                <CardTitle>{workflow.name}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm text-[rgb(var(--muted-foreground))]">
                <p>Key: {workflow.key}</p>
                <p>Trigger: {workflow.trigger_type}</p>
                <p>Status: {workflow.enabled ? "Enabled" : "Disabled"}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
