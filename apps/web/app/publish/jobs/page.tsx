import { apiFetch } from "../../../lib/api";
import { PublishJobsTable } from "./table";

type PublishJob = {
  id: string;
  provider: string;
  account_ref: string;
  status: string;
  attempts: number;
  external_id: string | null;
  last_error: string | null;
  created_at: string;
};

type OpsSettings = {
  connector_mode: "mock" | "live";
};

async function getJobs(): Promise<PublishJob[]> {
  return apiFetch<PublishJob[]>("/publish/jobs?limit=50&offset=0");
}

async function getOpsSettings(): Promise<OpsSettings> {
  try {
    return await apiFetch<OpsSettings>("/ops/settings");
  } catch {
    return { connector_mode: "mock" };
  }
}

export default async function PublishJobsPage() {
  const [jobs, settings] = await Promise.all([getJobs(), getOpsSettings()]);
  const liveMode = settings.connector_mode === "live";
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Publish Jobs</h1>
      <p className="mt-2 text-slate-300">Track queued and published content jobs.</p>
      <p className={`mt-3 rounded border px-3 py-2 text-sm ${liveMode ? "border-amber-500 text-amber-200" : "border-slate-700 text-slate-300"}`}>
        {liveMode ? "LIVE MODE ON - publishing can post to real connected accounts." : "LIVE MODE OFF - publishing uses mock adapters only."}
      </p>
      <PublishJobsTable jobs={jobs} />
    </main>
  );
}

