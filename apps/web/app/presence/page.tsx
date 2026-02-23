import { apiFetch } from "../../lib/api";
import { PresenceConsole } from "./presence-console";

type AuditRun = {
  id: string;
  status: string;
  summary_scores_json: { overall_score?: number; category_scores?: Record<string, number> };
  created_at: string;
};

type Finding = {
  id: string;
  source: string;
  category: string;
  severity: string;
  title: string;
  status: string;
};

type PresenceTask = {
  id: string;
  type: string;
  status: string;
  payload_json: Record<string, unknown>;
};

export default async function PresencePage() {
  const latest = await apiFetch<AuditRun | null>("/presence");
  const findings = await apiFetch<Finding[]>("/presence/findings?limit=20&offset=0");
  const tasks = await apiFetch<PresenceTask[]>("/presence/tasks?limit=20&offset=0");

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">Presence Health</h1>
      <p className="mt-2 text-slate-400">Run audits, track findings, and manage optimization tasks.</p>
      <PresenceConsole initialLatest={latest} initialFindings={findings} initialTasks={tasks} />
    </main>
  );
}
