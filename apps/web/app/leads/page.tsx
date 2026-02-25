import { apiFetch } from "../../lib/api";
import { LeadsConsole } from "./console";

type Lead = {
  id: string;
  source: string;
  status: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  tags_json: string[];
  created_at: string;
};

async function getLeads(): Promise<Lead[]> {
  return apiFetch<Lead[]>("/leads?limit=50&offset=0");
}

export default async function LeadsPage() {
  const leads = await getLeads();
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Leads</h1>
      <p className="mt-2 text-slate-300">Score, route, and apply nurture tasks from the unified lead engine.</p>
      <LeadsConsole initialLeads={leads} />
    </main>
  );
}

