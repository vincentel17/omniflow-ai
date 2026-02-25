import { apiFetch } from "../../lib/api";

type AuditRow = {
  id: string;
  action: string;
  target_type: string;
  target_id: string;
  created_at: string;
};

async function getAuditLogs(): Promise<AuditRow[]> {
  try {
    return await apiFetch<AuditRow[]>("/audit?limit=50&offset=0");
  } catch {
    return [];
  }
}

export default async function AuditPage() {
  const entries = await getAuditLogs();
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Audit Log</h1>
      <ul className="mt-6 space-y-2">
        {entries.map((entry) => (
          <li className="rounded border border-slate-800 p-3 text-sm" key={entry.id}>
            <p>
              <span className="font-semibold">{entry.action}</span> on {entry.target_type}
            </p>
            <p className="text-slate-400">
              {entry.target_id} - {new Date(entry.created_at).toLocaleString()}
            </p>
          </li>
        ))}
      </ul>
    </main>
  );
}
