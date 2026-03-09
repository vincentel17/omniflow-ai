import Link from "next/link";

import { getAgentContext, listAgentDefinitions, listAgentRuns } from "../../../lib/api";
import { Badge, ButtonGhost, Card, CardContent, CardHeader, CardTitle, EmptyState } from "../../../components/ui/primitives";
import { AgentsPageActions, AgentToggleButton } from "./page-actions";

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

export default async function AgentsPage() {
  const [contextResult, runs, definitions] = await Promise.all([
    getAgentContext().catch(() => null),
    listAgentRuns(8, 0).catch(() => []),
    listAgentDefinitions().catch(() => []),
  ]);
  const snapshot = contextResult?.snapshot;

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Agents</h1>
        <p className="page-subtitle">Supervisor + specialized agents propose plans and execute through workflow actions only.</p>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Guardrails</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-[rgb(var(--muted-foreground))]">
            <p>Max auto tier: {String(snapshot?.risk_limits?.max_auto_tier ?? "-")}</p>
            <p>Max plans/day: {String(snapshot?.risk_limits?.max_plans_per_day ?? "-")}</p>
            <p>Max steps/plan: {String(snapshot?.risk_limits?.max_steps_per_plan ?? "-")}</p>
            <p>Cooldown mins: {String(snapshot?.risk_limits?.cooldown_minutes ?? "-")}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Context Signals</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-[rgb(var(--muted-foreground))]">
            <p>Open threads: {String(snapshot?.inbox_summary?.open_threads ?? "-")}</p>
            <p>SLA breaches: {String(snapshot?.inbox_summary?.sla_breaches ?? "-")}</p>
            <p>New leads: {String(snapshot?.leads_summary?.new ?? "-")}</p>
            <p>Predictive lift: {String(snapshot?.optimization_signals?.predictive_lead_lift ?? "-")}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <AgentsPageActions />
            <Link href="/automations/agents/runs" className="inline-flex w-full">
              <ButtonGhost className="w-full">View Agent Runs</ButtonGhost>
            </Link>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Agent Definitions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {definitions.length === 0 ? (
            <p className="text-sm text-[rgb(var(--muted-foreground))]">No definitions found.</p>
          ) : (
            definitions.map((definition) => {
              const nextEnabled = !definition.enabled;
              return (
                <div key={definition.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[rgb(var(--border))] p-3">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold">{definition.name}</p>
                    <p className="text-xs text-[rgb(var(--muted-foreground))]">v{definition.version}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={definition.enabled ? "success" : "neutral"}>{definition.enabled ? "enabled" : "disabled"}</Badge>
                    <AgentToggleButton name={definition.name} nextEnabled={nextEnabled} />
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      {runs.length === 0 ? (
        <EmptyState title="No agent runs yet" description="Trigger an agent run to start seeing plans, approvals, and execution traces." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {runs.map((run) => (
            <Card key={run.id}>
              <CardHeader>
                <CardTitle className="text-sm">{run.agent_name}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <Badge tone={toneForStatus(run.status)}>{run.status}</Badge>
                <p className="font-mono text-xs text-[rgb(var(--muted-foreground))]">{run.id}</p>
                <p className="text-xs text-[rgb(var(--muted-foreground))]">{new Date(run.created_at).toLocaleString()}</p>
                <Link href={`/automations/agents/runs/${run.id}`} className="text-xs text-[rgb(var(--primary))] underline">
                  Open run
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
