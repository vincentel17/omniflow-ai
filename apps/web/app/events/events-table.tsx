"use client";

import { useMemo, useState } from "react";

import { Badge, ButtonGhost, DataTable, EmptyState, Input, Pagination, Select } from "../../components/ui/primitives";

type EventRow = {
  id: string;
  type: string;
  source: string;
  channel: string;
  created_at: string;
};

const PAGE_SIZE = 12;

export function EventsTable({ events }: { events: EventRow[] }) {
  const [query, setQuery] = useState("");
  const [channel, setChannel] = useState("all");
  const [page, setPage] = useState(1);

  const channels = useMemo(() => ["all", ...Array.from(new Set(events.map((event) => event.channel)))], [events]);

  const filtered = useMemo(
    () =>
      events.filter((event) => {
        const matchesQuery = `${event.type} ${event.source} ${event.channel}`.toLowerCase().includes(query.toLowerCase());
        const matchesChannel = channel === "all" || event.channel === channel;
        return matchesQuery && matchesChannel;
      }),
    [events, query, channel]
  );

  const start = (page - 1) * PAGE_SIZE;
  const paged = filtered.slice(start, start + PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div className="surface-card p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <Input onChange={(event) => { setPage(1); setQuery(event.target.value); }} placeholder="Search by type, source, or channel" value={query} />
          <Select onChange={(event) => { setPage(1); setChannel(event.target.value); }} value={channel}>
            {channels.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </Select>
          <ButtonGhost onClick={() => { setQuery(""); setChannel("all"); setPage(1); }} type="button">Reset filters</ButtonGhost>
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="No matching events" description="Try broadening your filters or trigger a mock ingest run." />
      ) : (
        <div className="surface-card overflow-hidden">
          <div className="overflow-x-auto">
            <DataTable>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Channel</th>
                  <th>Source</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {paged.map((event) => (
                  <tr key={event.id}>
                    <td className="font-medium">{event.type}</td>
                    <td><Badge tone="info">{event.channel}</Badge></td>
                    <td>{event.source}</td>
                    <td>{new Date(event.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
          <div className="p-4">
            <Pagination
              hasNext={start + PAGE_SIZE < filtered.length}
              onNext={() => setPage((value) => value + 1)}
              onPrev={() => setPage((value) => Math.max(1, value - 1))}
              page={page}
            />
          </div>
        </div>
      )}
    </div>
  );
}
