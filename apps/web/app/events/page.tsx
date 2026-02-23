import { apiFetch } from "../../lib/api";

type EventRow = {
  id: string;
  type: string;
  source: string;
  channel: string;
  created_at: string;
};

async function getEvents(): Promise<EventRow[]> {
  return apiFetch<EventRow[]>("/events?limit=50&offset=0");
}

export default async function EventsPage() {
  const events = await getEvents();
  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">Events</h1>
      <ul className="mt-6 space-y-2">
        {events.map((event) => (
          <li className="rounded border border-slate-800 p-3 text-sm" key={event.id}>
            <p>
              <span className="font-semibold">{event.type}</span> via {event.channel}/{event.source}
            </p>
            <p className="text-slate-400">{new Date(event.created_at).toLocaleString()}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
