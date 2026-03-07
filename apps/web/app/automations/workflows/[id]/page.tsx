import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch } from "../../../../lib/api";

type WorkflowDefinition = {
  id: string;
  key: string;
  name: string;
  enabled: boolean;
  trigger_type: string;
  managed_by_pack: boolean;
  updated_at: string;
  definition_json: Record<string, unknown>;
};

type WorkflowDetailPageProps = {
  params: Promise<{ id: string }>;
};

const triggerLabel: Record<string, string> = {
  event: "Event trigger",
  schedule: "Schedule trigger",
};

export default async function WorkflowDetailPage({ params }: WorkflowDetailPageProps) {
  const { id } = await params;
  let workflow: WorkflowDefinition | null = null;

  try {
    workflow = await apiFetch<WorkflowDefinition>(`/workflows/${id}`);
  } catch {
    notFound();
  }

  if (!workflow) {
    notFound();
  }

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6 lg:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[var(--muted-foreground)]">
              Automation workflow
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-[var(--foreground)]">{workflow.name}</h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Workflow key <span className="font-medium text-[var(--foreground)]">{workflow.key}</span>
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link className="button-secondary" href="/automations/workflows">
              Back to workflows
            </Link>
            <Link className="button-secondary" href="/automations/runs">
              View workflow runs
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Status" value={workflow.enabled ? "Enabled" : "Disabled"} />
        <MetricCard label="Trigger" value={triggerLabel[workflow.trigger_type] ?? workflow.trigger_type} />
        <MetricCard label="Managed by pack" value={workflow.managed_by_pack ? "Yes" : "No"} />
        <MetricCard label="Updated" value={formatDateTime(workflow.updated_at)} />
      </section>

      <section className="surface-card p-6 lg:p-8">
        <div className="space-y-3">
          <h2 className="text-xl font-semibold text-[var(--foreground)]">Definition JSON</h2>
          <p className="text-sm text-[var(--muted-foreground)]">
            This is the validated workflow definition currently active for the selected org.
          </p>
          <pre className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--border)] bg-[color-mix(in_oklab,var(--surface)_92%,black_8%)] p-4 text-xs text-[var(--muted-foreground)]">
            {JSON.stringify(workflow.definition_json, null, 2)}
          </pre>
        </div>
      </section>
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="surface-panel space-y-2 p-5">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--muted-foreground)]">{label}</p>
      <p className="text-lg font-semibold text-[var(--foreground)]">{value}</p>
    </article>
  );
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

