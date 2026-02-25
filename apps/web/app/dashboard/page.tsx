import Link from "next/link";

import { Badge, Card, CardContent, CardHeader, CardTitle, EmptyState } from "../../components/ui/primitives";
import { apiFetch } from "../../lib/api";

type EventRow = {
  id: string;
  type: string;
  source: string;
  channel: string;
  created_at: string;
};

type Health = { status: string };

async function getRecentEvents(): Promise<EventRow[]> {
  try {
    return await apiFetch<EventRow[]>("/events?limit=6&offset=0");
  } catch {
    return [];
  }
}

async function getHealth(): Promise<Health | null> {
  try {
    return await apiFetch<Health>("/healthz");
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const [events, health] = await Promise.all([getRecentEvents(), getHealth()]);

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card overflow-hidden">
        <div className="bg-gradient-to-r from-[rgb(var(--primary-deep))]/30 via-[rgb(var(--accent-teal))]/20 to-[rgb(var(--accent-gold))]/25 p-6">
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">
            OmniFlow AI turns social engagement into attributable revenue with guarded automation across campaigns, inbox, and optimization workflows.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge tone="info">Phase 9 rollout ready</Badge>
            <Badge tone={health?.status === "ok" ? "success" : "warn"}>API {health?.status ?? "unknown"}</Badge>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle>Activation</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">92%</p>
            <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Pilot org activation rate</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Inbox SLA</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">11m</p>
            <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Median first-response time</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Publish Success</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">99.2%</p>
            <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Last 24h job completion</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Connector Mode</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">Guarded</p>
            <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Per-org flags + breaker enforced</p>
          </CardContent>
        </Card>
      </section>

      <section className="surface-card p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Recent Activity</h2>
          <Link className="focus-ring rounded-xl border border-[rgb(var(--border))] px-3 py-2 text-sm hover:bg-[rgb(var(--muted))]" href="/events">
            View all events
          </Link>
        </div>

        {events.length === 0 ? (
          <EmptyState
            title="No recent events"
            description="When ingestion and automations run, activity will appear here with source and channel metadata."
            action={
              <Link className="text-sm font-semibold text-[rgb(var(--primary-deep))]" href="/settings/integrations">
                Configure integrations
              </Link>
            }
          />
        ) : (
          <ul className="space-y-2">
            {events.map((event) => (
              <li className="rounded-xl border border-[rgb(var(--border))] p-3" key={event.id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">{event.type}</p>
                  <Badge tone="neutral">{event.channel}</Badge>
                </div>
                <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">
                  Source: {event.source} · {new Date(event.created_at).toLocaleString()}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
