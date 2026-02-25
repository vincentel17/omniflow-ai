import { apiFetch } from "../../lib/api";
import { EventsTable } from "./events-table";

type EventRow = {
  id: string;
  type: string;
  source: string;
  channel: string;
  created_at: string;
};

async function getEvents(): Promise<EventRow[]> {
  return apiFetch<EventRow[]>("/events?limit=200&offset=0");
}

export default async function EventsPage() {
  const events = await getEvents();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Events</h1>
        <p className="page-subtitle">Track normalized event streams across channels with searchable metadata and audit-friendly timestamps.</p>
      </section>
      <EventsTable events={events} />
    </main>
  );
}
