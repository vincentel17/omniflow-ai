import { apiFetch } from "../../../lib/api";

type AuditRun = {
  id: string;
  status: string;
  summary_scores_json: { overall_score?: number };
  created_at: string;
};

export default async function PresenceAuditsPage() {
  const audits = await apiFetch<AuditRun[]>("/presence/audits?limit=50&offset=0");
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Presence Audit Runs</h1>
      <ul className="mt-6 space-y-2">
        {audits.map((audit) => (
          <li className="rounded border border-slate-800 p-3" key={audit.id}>
            <p className="font-medium">
              {audit.status} | score: {audit.summary_scores_json.overall_score ?? "n/a"}
            </p>
            <p className="text-sm text-slate-400">{new Date(audit.created_at).toLocaleString()}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}

