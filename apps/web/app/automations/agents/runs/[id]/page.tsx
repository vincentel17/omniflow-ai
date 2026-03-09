import Link from "next/link";
import { notFound } from "next/navigation";

import { getAgentRun, listApprovals } from "../../../../../lib/api";
import { Badge, Card, CardContent, CardHeader, CardTitle } from "../../../../../components/ui/primitives";
import { AgentRunActions } from "./run-actions";

type PageProps = {
  params: Promise<{ id: string }>;
};

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

export default async function AgentRunDetailPage({ params }: PageProps) {
  const { id } = await params;
  const run = await getAgentRun(id).catch(() => null);
  if (!run) {
    notFound();
  }

  const approvals = await listApprovals(100, 0, "pending").catch(() => []);
  const relatedApprovals = approvals.filter(
    (item) => (item.entity_type === "agent_run" || item.entity_type === "agent_plan") && item.entity_id === run.id,
  );

  const planSteps = Array.isArray((run.plan_json as { steps?: unknown[] }).steps)
    ? ((run.plan_json as { steps: Array<Record<string, unknown>> }).steps ?? [])
    : [];

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Agent Run Detail</h1>
        <p className="page-subtitle">Plan, context summary, approval state, and execution controls for this run.</p>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>{run.agent_name}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-[rgb(var(--muted-foreground))]">
            <Badge tone={toneForStatus(run.status)}>{run.status}</Badge>
            <p>Version: {run.agent_version}</p>
            <p>Trigger: {run.trigger_type}</p>
            <p>Started: {run.started_at ? new Date(run.started_at).toLocaleString() : "-"}</p>
            <p>Finished: {run.finished_at ? new Date(run.finished_at).toLocaleString() : "-"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Context Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-[rgb(var(--muted-foreground))]">
            <p>Pack: {String(run.context_snapshot_json?.active_pack_slug ?? "-")}</p>
            <p>Compliance: {String(run.context_snapshot_json?.compliance_mode ?? "-")}</p>
            <p>Open threads: {String((run.context_snapshot_json?.inbox_summary as Record<string, unknown> | undefined)?.open_threads ?? "-")}</p>
            <p>New leads: {String((run.context_snapshot_json?.leads_summary as Record<string, unknown> | undefined)?.new ?? "-")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <AgentRunActions runId={id} />
            <Link className="text-[rgb(var(--primary))] underline" href="/automations/agents/runs">
              Back to runs
            </Link>
            <Link className="text-[rgb(var(--primary))] underline" href="/automations/agents">
              Agents dashboard
            </Link>
          </CardContent>
        </Card>
      </div>

      <section className="surface-card p-4">
        <h2 className="text-base font-semibold">Plan Steps</h2>
        {planSteps.length === 0 ? (
          <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">No steps recorded.</p>
        ) : (
          <div className="mt-3 space-y-3">
            {planSteps.map((step) => (
              <div key={String(step.step_id ?? "step")} className="rounded-xl border border-[rgb(var(--border))] p-3 text-sm">
                <p className="font-medium">{String(step.action_type ?? "unknown")}</p>
                <p className="text-[rgb(var(--muted-foreground))]">Target: {String(step.target_ref ?? "-")}</p>
                <p className="text-[rgb(var(--muted-foreground))]">Risk tier: {String(step.risk_tier ?? "-")}</p>
                <p className="text-[rgb(var(--muted-foreground))]">Expected: {String(step.expected_outcome ?? "-")}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="surface-card p-4">
        <h2 className="text-base font-semibold">Pending Approvals</h2>
        {relatedApprovals.length === 0 ? (
          <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">No pending approvals for this run.</p>
        ) : (
          <div className="mt-3 space-y-3">
            {relatedApprovals.map((approval) => (
              <div key={approval.id} className="rounded-xl border border-[rgb(var(--border))] p-3 text-sm">
                <p className="font-mono text-xs">{approval.id}</p>
                <p className="text-[rgb(var(--muted-foreground))]">Entity: {approval.entity_type}</p>
                <div className="mt-3 flex gap-2">
                  <AgentRunActions approvalId={approval.id} runId={id} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

