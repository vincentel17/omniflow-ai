import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch } from "../../../../lib/api";
import { requireAuthSession } from "../../../../lib/server-auth";

type WorkflowRunDetail = {
  id: string;
  workflow_id: string;
  status: string;
  loop_guard_hits: number;
  started_at: string | null;
  summary_json: Record<string, unknown> | null;
  error_json: Record<string, unknown> | null;
};

type WorkflowRunDetailPageProps = {
  params: Promise<{ id: string }>;
};

export default async function WorkflowRunDetailPage({ params }: WorkflowRunDetailPageProps) {
  await requireAuthSession();
  const { id } = await params;
  let run: WorkflowRunDetail | null = null;

  try {
    run = await apiFetch<WorkflowRunDetail>(`/workflows/runs/${id}`);
  } catch {
    notFound();
  }

  if (!run) {
    notFound();
  }

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6 lg:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[var(--muted-foreground)]">Workflow run</p>
            <h1 className="text-3xl font-semibold tracking-tight text-[var(--foreground)]">Run {run.id.slice(0, 8)}</h1>
            <p className="text-sm text-[var(--muted-foreground)]">Inspect workflow execution state, output, and any recorded errors.</p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link className="button-secondary" href="/automations/runs">
              Back to runs
            </Link>
            <Link className="button-secondary" href={`/automations/workflows/${run.workflow_id}`}>
              Open workflow
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Status" value={run.status} />
        <MetricCard label="Workflow" value={run.workflow_id.slice(0, 8)} />
        <MetricCard label="Loop guards" value={String(run.loop_guard_hits)} />
        <MetricCard label="Started" value={formatDateTime(run.started_at)} />
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <article className="surface-card space-y-3 p-6 lg:p-8">
          <h2 className="text-xl font-semibold text-[var(--foreground)]">Summary JSON</h2>
          <pre className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--border)] bg-[color-mix(in_oklab,var(--surface)_92%,black_8%)] p-4 text-xs text-[var(--muted-foreground)]">
            {JSON.stringify(run.summary_json ?? {}, null, 2)}
          </pre>
        </article>
        <article className="surface-card space-y-3 p-6 lg:p-8">
          <h2 className="text-xl font-semibold text-[var(--foreground)]">Error JSON</h2>
          <pre className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--border)] bg-[color-mix(in_oklab,var(--surface)_92%,black_8%)] p-4 text-xs text-[var(--muted-foreground)]">
            {JSON.stringify(run.error_json ?? {}, null, 2)}
          </pre>
        </article>
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

function formatDateTime(value: string | null) {
  if (!value) {
    return "Not started";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

