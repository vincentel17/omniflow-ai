import Link from "next/link";

import { listAgentRuns } from "../../../../lib/api";
import { Badge, DataTable, EmptyState } from "../../../../components/ui/primitives";

function toneForStatus(status: string): "neutral" | "success" | "warn" | "danger" | "info" {
  if (status === "succeeded") {
    return "success";
  }
  if (status === "failed" || status === "blocked") {
    return "danger";
  }
  if (status === "approved" || status === "executing") {
    return "info";
  }
  if (status === "planned" || status === "proposed") {
    return "warn";
  }
  return "neutral";
}

export default async function AgentRunsPage() {
  const runs = await listAgentRuns(50, 0).catch(() => []);

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Agent Runs</h1>
        <p className="page-subtitle">Planned, approval-gated, and executed AI agent plans with status traceability.</p>
      </section>

      {runs.length === 0 ? (
        <EmptyState title="No agent runs" description="Runs appear after manual triggers or scheduled orchestrator jobs." />
      ) : (
        <div className="surface-card p-4">
          <DataTable>
            <thead>
              <tr>
                <th>Run</th>
                <th>Agent</th>
                <th>Status</th>
                <th>Trigger</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="font-mono text-xs">
                    <Link href={`/automations/agents/runs/${run.id}`} className="text-[rgb(var(--primary))] underline">
                      {run.id}
                    </Link>
                  </td>
                  <td>{run.agent_name}</td>
                  <td>
                    <Badge tone={toneForStatus(run.status)}>{run.status}</Badge>
                  </td>
                  <td>{run.trigger_type}</td>
                  <td>{new Date(run.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      )}
    </main>
  );
}
