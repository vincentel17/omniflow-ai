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

async function getJobs(): Promise<PublishJob[]> {
  return apiFetch<PublishJob[]>("/publish/jobs?limit=50&offset=0");
}

export default async function PublishJobsPage() {
  const jobs = await getJobs();
  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">Publish Jobs</h1>
      <p className="mt-2 text-slate-300">Track queued and published content jobs.</p>
      <PublishJobsTable jobs={jobs} />
    </main>
  );
}
